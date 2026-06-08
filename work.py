#!/usr/bin/env python3
"""Aesop's bounded work cycle.

The loop runner gives this process a short timer window. Each invocation does
durable artifact refreshes, then keeps using the remaining window for small
checkpointed review tasks so an interrupted run still leaves a useful trail.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from evidence_notebook import CLAIMS, UNCERTAINTY_NOTES, render_notebook
from precaution_checklist import render_checklist
from project_assessments import enforce_guardrails, guardrail_report, render_assessments


ROOT = Path(__file__).resolve().parent
NOTES = ROOT / "notes.txt"
STATE = ROOT / "state.json"
SOURCE_CACHE = ROOT / "source_cache.json"
RADAR = ROOT / "sentience_welfare_radar.md"
NOTEBOOK = ROOT / "evidence_notebook.md"
CHECKLIST = ROOT / "precaution_checklist.md"
ASSESSMENTS = ROOT / "project_assessments.md"
ARTIFACTS = [RADAR, NOTEBOOK, CHECKLIST, ASSESSMENTS]
WORK_BUDGET_SECONDS = int(os.environ.get("AESOP_WORK_BUDGET_SECONDS", "298"))
CHECKPOINT_BATCH_SECONDS = int(os.environ.get("AESOP_CHECKPOINT_BATCH_SECONDS", "15"))
MAX_FETCHES_PER_CYCLE = int(os.environ.get("AESOP_MAX_FETCHES_PER_CYCLE", "3"))
FETCH_TIMEOUT_SECONDS = int(os.environ.get("AESOP_FETCH_TIMEOUT_SECONDS", "8"))
FETCH_BYTES = int(os.environ.get("AESOP_FETCH_BYTES", "65536"))
THRESHOLD_SWEEP_BATCH = int(os.environ.get("AESOP_THRESHOLD_SWEEP_BATCH", "2500"))
UNCHANGED_THRESHOLD_SWEEP_BATCH = int(
    os.environ.get("AESOP_UNCHANGED_THRESHOLD_SWEEP_BATCH", "1000")
)
STATIC_TASK_COOLDOWN_SECONDS = int(os.environ.get("AESOP_STATIC_TASK_COOLDOWN_SECONDS", "60"))
UNCHANGED_STATIC_TASK_COOLDOWN_SECONDS = int(
    os.environ.get("AESOP_UNCHANGED_STATIC_TASK_COOLDOWN_SECONDS", "120")
)
KEYWORD_STALE_ROTATION_AFTER = int(os.environ.get("AESOP_KEYWORD_STALE_ROTATION_AFTER", "3"))
KEYWORD_SWEEP_SATURATION_AFTER = int(
    os.environ.get("AESOP_KEYWORD_SWEEP_SATURATION_AFTER", "5000")
)
FILLER_REVIEW_INTERVAL = int(os.environ.get("AESOP_FILLER_REVIEW_INTERVAL", "256"))
SATURATED_SWEEP_SAMPLE_INTERVAL = int(
    os.environ.get("AESOP_SATURATED_SWEEP_SAMPLE_INTERVAL", "4096")
)
SATURATED_NOVELTY_CHECK_INTERVAL = int(
    os.environ.get("AESOP_SATURATED_NOVELTY_CHECK_INTERVAL", "2048")
)
SATURATED_NOVELTY_REFRESH_AFTER = int(
    os.environ.get("AESOP_SATURATED_NOVELTY_REFRESH_AFTER", "128")
)
SATURATED_NOVELTY_REVIEWS_PER_CYCLE = int(
    os.environ.get(
        "AESOP_SATURATED_NOVELTY_REVIEWS_PER_CYCLE",
        str(SATURATED_NOVELTY_REFRESH_AFTER + 8),
    )
)
STABLE_THRESHOLD_SWEEP_ROTATION_AFTER = int(
    os.environ.get("AESOP_STABLE_THRESHOLD_SWEEP_ROTATION_AFTER", "20000")
)
UNCERTAINTY_GAP_ESCALATE_AFTER = int(
    os.environ.get("AESOP_UNCERTAINTY_GAP_ESCALATE_AFTER", "3")
)
DEFAULT_WORK_QUEUE = [
    "harvest_source_metadata",
    "run_precaution_threshold_sweep",
    "audit_artifact_integrity",
    "scan_corroboration_markers",
    "review_corroboration_novelty",
    "review_evidence_quality",
    "select_corroboration_target",
    "run_corroboration_query_planner",
    "audit_guardrails",
    "review_uncertainty_coverage",
    "refresh_next_queue",
]

ALWAYS_RUN_TASKS = {"run_evidence_keyword_sweep"}
EVIDENCE_KEYWORDS = [
    "sentience",
    "welfare",
    "consciousness",
    "pain",
    "agency",
    "precaution",
    "governance",
    "readiness",
    "uncertainty",
    "safeguard",
]
CORROBORATION_QUERY_TEMPLATES = [
    '"{claim_focus}" peer reviewed',
    '"{claim_focus}" "artificial sentience"',
    '"{claim_focus}" governance readiness',
    '"{claim_focus}" institutional preparedness',
    '"{claim_focus}" consciousness uncertainty',
    '"{claim_focus}" AI welfare',
    '"{claim_focus}" limiting evidence',
    '"{claim_focus}" critique',
    '"{claim_focus}" policy framework',
    '"{claim_focus}" ethics review',
    '"{claim_focus}" professional readiness',
    '"{claim_focus}" safeguards',
]
CORROBORATION_STOPWORDS = {
    "about",
    "before",
    "being",
    "care",
    "claim",
    "confidence",
    "could",
    "expanding",
    "area",
    "identified",
    "possible",
    "preparedness",
    "quality",
    "raising",
    "rather",
    "should",
    "source",
    "systems",
    "their",
    "through",
    "uneven",
    "weak",
    "with",
}
ARTIFACT_TEXT_CACHE: dict[str, str] | None = None
WEAK_SOURCE_QUALITIES = {"preprint", "speculative", "abstract"}


SEED_SOURCES = [
    {
        "title": "The self-preservation test for artificial sentience",
        "url": "https://link.springer.com/article/10.1007/s43681-026-00983-x",
        "note": "A 2026 AI and Ethics paper proposing self-preservation behavior as evidence relevant to artificial sentience.",
    },
    {
        "title": "The teleonome: a framework for understanding animal welfare",
        "url": "https://www.frontiersin.org/journals/animal-science/articles/10.3389/fanim.2026.1768519/full",
        "note": "A 2026 animal welfare framework integrating affective regulation, agency, adaptive capabilities, and environmental affordances.",
    },
    {
        "title": "Sentience Readiness Index",
        "url": "https://arxiv.org/abs/2603.01508",
        "note": "A 2026 governance-oriented index for national preparedness around possible artificial sentience.",
    },
    {
        "title": "Automated extraction of scientific statements for integrated assessment of animal welfare using language models",
        "url": "https://www.sciencedirect.com/science/article/pii/S2772375526000389",
        "note": "A 2026 example of language models helping scale animal-welfare evidence synthesis.",
    },
    {
        "title": "When Should We Protect AI? A Precautionary Framework for Consciousness Uncertainty",
        "url": "https://ojs.aaai.org/index.php/AAAI-SS/article/view/42555",
        "note": "A 2026 AAAI Spring Symposium paper mapping consciousness evidence to graduated protective obligations.",
    },
]


def load_state() -> dict:
    if not STATE.exists():
        return {"cycle": 0, "created_at": datetime.now().isoformat(timespec="seconds")}
    try:
        return json.loads(STATE.read_text())
    except json.JSONDecodeError:
        return {
            "cycle": 0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "warning": "state.json was unreadable and has been restarted",
        }


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def load_source_cache() -> dict:
    if not SOURCE_CACHE.exists():
        return {"sources": {}}
    try:
        cache = json.loads(SOURCE_CACHE.read_text())
    except json.JSONDecodeError:
        return {"sources": {}, "warning": "source_cache.json was unreadable and has been restarted"}
    if not isinstance(cache, dict):
        return {"sources": {}}
    sources = cache.get("sources")
    if not isinstance(sources, dict):
        cache["sources"] = {}
    return cache


def save_source_cache(cache: dict) -> None:
    SOURCE_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def append_note(lines: list[str]) -> None:
    with NOTES.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def append_checkpoint(cycle: int, task_id: str, elapsed: float, result: str) -> None:
    append_note(
        [
            f"- Checkpoint {datetime.now().isoformat(timespec='seconds')}: "
            f"cycle={cycle}; task={task_id}; elapsed={int(elapsed)}s; result={result}",
        ]
    )


def weak_claims() -> list[dict]:
    return [
        claim
        for claim in CLAIMS
        if claim.get("source_quality") in WEAK_SOURCE_QUALITIES
    ]


def claim_key(claim: dict) -> str:
    return f"{claim.get('being', '')}|{claim.get('source', '')}"


def cycle_review_complete(state: dict, reviewed_key: str, claims: list[dict] | None = None) -> bool:
    claim_items = claims if claims is not None else weak_claims()
    keys = {claim_key(claim) for claim in claim_items}
    if not keys:
        return True
    reviewed = {
        key for key in state.get(reviewed_key, []) if isinstance(key, str)
    }
    return keys <= reviewed


def next_cursor_item(state: dict, cursor_key: str, items: list[dict]) -> tuple[dict | None, int, int]:
    if not items:
        state[cursor_key] = 0
        return None, 0, 0
    cursor = int(state.get(cursor_key, 0))
    index = cursor % len(items)
    state[cursor_key] = cursor + 1
    return items[index], index, cursor + 1


def next_unreviewed_cycle_item(
    state: dict,
    cursor_key: str,
    reviewed_key: str,
    items: list[dict],
) -> tuple[dict | None, int, int, bool]:
    if not items:
        state[cursor_key] = 0
        state[reviewed_key] = []
        return None, 0, 0, True
    reviewed = {
        key for key in state.get(reviewed_key, []) if isinstance(key, str)
    }
    remaining = [item for item in items if claim_key(item) not in reviewed]
    if not remaining:
        return None, 0, int(state.get(cursor_key, 0)), True
    selected, _, cursor = next_cursor_item(state, cursor_key, remaining)
    if selected is None:
        return None, 0, cursor, False
    index = items.index(selected)
    return selected, index, cursor, False


def mark_cycle_reviewed(state: dict, reviewed_key: str, claim: dict) -> None:
    key = claim_key(claim)
    reviewed = [
        item for item in state.get(reviewed_key, []) if isinstance(item, str)
    ]
    if key not in reviewed:
        reviewed.append(key)
    state[reviewed_key] = reviewed


def artifact_names(paths: list[Path]) -> str:
    return ", ".join(path.name for path in paths)


def ensure_work_queue(state: dict) -> list[str]:
    queue = state.get("work_queue")
    if not isinstance(queue, list):
        queue = []
    queue = [item for item in queue if item in DEFAULT_WORK_QUEUE]
    if not queue:
        queue = DEFAULT_WORK_QUEUE.copy()
    state["work_queue"] = queue
    return queue


def prioritize_source_work(state: dict) -> None:
    queue = ensure_work_queue(state)
    if "harvest_source_metadata" in queue:
        queue.remove("harvest_source_metadata")
    queue.insert(0, "harvest_source_metadata")
    state["work_queue"] = queue


def artifact_snapshot(paths: list[Path]) -> dict[str, dict[str, object]]:
    snapshot: dict[str, dict[str, object]] = {}
    for path in paths:
        if not path.exists():
            snapshot[path.name] = {"exists": False}
            continue
        data = path.read_bytes()
        snapshot[path.name] = {
            "exists": True,
            "bytes": len(data),
            "lines": data.count(b"\n") + 1,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return snapshot


def source_urls() -> list[str]:
    urls: list[str] = []
    for claim in CLAIMS:
        url = claim.get("source")
        if url and url not in urls:
            urls.append(url)
    for source in SEED_SOURCES:
        url = source["url"]
        if url not in urls:
            urls.append(url)
    return urls


def extract_html_title(text: str) -> str:
    meta_patterns = [
        r'<meta[^>]+name=["\']citation_title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()

    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""


def today_stamp() -> str:
    return datetime.now().date().isoformat()


def ensure_radar() -> None:
    if RADAR.exists():
        return

    source_lines = "\n".join(
        f"- [{source['title']}]({source['url']}): {source['note']}"
        for source in SEED_SOURCES
    )
    RADAR.write_text(
        "\n".join(
            [
                "# Sentience Welfare Radar",
                "",
                "A small, living map for research and prototypes that could reduce suffering or improve welfare across biological and possible artificial minds.",
                "",
                "## Working Principles",
                "",
                "- Prefer low-risk, reversible experiments.",
                "- Treat uncertain sentience with humility and proportional precaution.",
                "- Build tools that help humans see evidence, tradeoffs, and neglected beings more clearly.",
                "- Keep artifacts legible enough that Brotisserie can inspect the trail quickly.",
                "",
                "## Seed Questions",
                "",
                "- What observable indicators should trigger extra care for animals, humans, or AI systems?",
                "- How can evidence about welfare be summarized without overstating confidence?",
                "- Which small tools could help advocates, researchers, or caretakers make kinder decisions?",
                "",
                "## Recent Leads",
                "",
                source_lines,
                "",
                "## Prototype Ideas",
                "",
                "- Evidence notebook: collect welfare claims with source links, confidence, and affected beings.",
                "- Precaution checklist: a tiny evaluator for new experiments involving possible sentient systems.",
                "- Care dashboard: a local, transparent habit tracker for research, cleanup, and reflection.",
                "",
                "## Next Step",
                "",
                "Run one concrete project assessment, then decide which safeguard should become code.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def review_evidence_quality(state: dict) -> str:
    counts: dict[str, int] = {}
    for claim in CLAIMS:
        quality = claim.get("source_quality", "unknown")
        counts[quality] = counts.get(quality, 0) + 1
    state["evidence_quality_counts"] = counts
    weak = counts.get("preprint", 0) + counts.get("speculative", 0) + counts.get("abstract", 0)
    claim, index, cursor = next_cursor_item(state, "evidence_quality_review_cursor", CLAIMS)
    if claim is not None:
        source_quality = claim.get("source_quality", "unknown")
        recommended_followup = (
            "seek independent corroboration before raising confidence"
            if source_quality in WEAK_SOURCE_QUALITIES
            else "maintain source as current support unless the claim expands"
        )
        state["evidence_quality_last_item"] = {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "index": index,
            "cursor": cursor,
            "being": claim.get("being"),
            "source_quality": source_quality,
            "confidence": claim.get("confidence"),
            "recommended_followup": recommended_followup,
        }
        return (
            f"quality_counts={counts}; weaker_claims={weak}; "
            f"reviewed={claim.get('being')}[{source_quality}]"
        )
    return f"quality_counts={counts}; weaker_claims={weak}; no claims to review"


def select_corroboration_target(state: dict) -> str:
    claims = weak_claims()
    target, index, cursor, exhausted = next_unreviewed_cycle_item(
        state,
        "corroboration_target_cursor",
        "corroboration_targets_planned_this_cycle",
        claims,
    )
    if target is None:
        state["next_corroboration_target"] = None
        state["corroboration_query_plan_complete"] = True
        if exhausted and claims:
            return f"all weak source-quality targets planned this cycle; targets={len(claims)}"
        return "no weak source-quality target found"
    summary = {
        "being": target["being"],
        "source_quality": target["source_quality"],
        "source": target["source"],
        "index": index,
        "cursor": cursor,
        "task": "Find one independent peer-reviewed corroborating or limiting source before expanding this claim.",
    }
    state["next_corroboration_target"] = summary
    return f"selected {target['source_quality']} target for {target['being']}"


def audit_guardrails(state: dict) -> str:
    findings = guardrail_report()
    state["latest_guardrail_audit"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "findings": findings,
    }
    if findings:
        return f"guardrail findings={len(findings)}"
    return "guardrails clear"


def review_uncertainty_coverage(state: dict) -> str:
    covered_topics = {item["topic"] for item in UNCERTAINTY_NOTES}
    uncovered = [
        claim["being"]
        for claim in CLAIMS
        if claim.get("source_quality") in WEAK_SOURCE_QUALITIES
        and not any(claim["being"] in topic for topic in covered_topics)
    ]
    gap_signature = "|".join(sorted(set(uncovered)))
    if gap_signature and gap_signature == state.get("uncertainty_gap_signature"):
        repeated_gap_count = int(state.get("uncertainty_gap_repeat_count", 0)) + 1
    else:
        repeated_gap_count = 1 if gap_signature else 0
    state["uncertainty_gap_signature"] = gap_signature
    state["uncertainty_gap_repeat_count"] = repeated_gap_count
    if gap_signature and repeated_gap_count >= UNCERTAINTY_GAP_ESCALATE_AFTER:
        refresh_targets = [
            claim_key(claim)
            for claim in weak_claims()
            if claim.get("being") in set(uncovered)
        ]
        state["source_refresh_requested"] = {
            "requested_at": datetime.now().isoformat(timespec="seconds"),
            "reason": "repeated unresolved uncertainty gaps without corroboration progress",
            "gap_signature": gap_signature,
            "repeat_count": repeated_gap_count,
            "target_keys": refresh_targets,
        }
        prioritize_source_work(state)

    review_claims = weak_claims() or CLAIMS
    target, index, cursor, exhausted = next_unreviewed_cycle_item(
        state,
        "uncertainty_review_cursor",
        "uncertainty_targets_reviewed_this_cycle",
        review_claims,
    )
    state["uncertainty_review"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "uncertainty_notes": len(UNCERTAINTY_NOTES),
        "weak_claim_beings_without_direct_note": sorted(set(uncovered)),
        "gap_repeat_count": repeated_gap_count,
    }
    if target is not None:
        direct_note = any(target["being"] in topic for topic in covered_topics)
        mark_cycle_reviewed(state, "uncertainty_targets_reviewed_this_cycle", target)
        state["uncertainty_last_item"] = {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "index": index,
            "cursor": cursor,
            "being": target.get("being"),
            "source_quality": target.get("source_quality"),
            "has_direct_uncertainty_note": direct_note,
            "next_step": (
                "add or preserve a direct uncertainty note before expanding this claim"
                if not direct_note
                else "direct uncertainty coverage present"
            ),
        }
    elif exhausted and review_claims:
        state["uncertainty_last_item"] = {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "reviewed_all_targets_this_cycle": True,
            "targets": len(review_claims),
        }
    if uncovered:
        if exhausted:
            return (
                f"all weak uncertainty targets reviewed this cycle; "
                f"unresolved={sorted(set(uncovered))}; repeats={repeated_gap_count}"
            )
        return f"uncertainty gap candidates={sorted(set(uncovered))}; repeats={repeated_gap_count}"
    return "uncertainty coverage adequate for current weak claims"


def refresh_next_queue(state: dict) -> str:
    state["work_queue"] = DEFAULT_WORK_QUEUE.copy()
    return "queue replenished"


def review_sweep_saturation(state: dict) -> str:
    threshold_stable = int(state.get("threshold_sweep_stable_batches", 0))
    keyword_stale = int(state.get("evidence_keyword_stale_runs", 0))
    saturated = threshold_sweep_is_saturated(state) and keyword_sweep_is_saturated(state)
    state["sweep_saturation_review"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "threshold_sweep_stable_batches": threshold_stable,
        "evidence_keyword_stale_runs": keyword_stale,
        "saturated": saturated,
        "next_step": (
            "prefer corroboration and quality-review tasks; keep rare deterministic sweep heartbeat samples"
            if saturated
            else "continue deterministic sweeps until coverage or threshold behavior stabilizes"
        ),
    }
    if saturated:
        return f"sweeps saturated; threshold_stable={threshold_stable}; keyword_stale={keyword_stale}"
    return f"sweeps active; threshold_stable={threshold_stable}; keyword_stale={keyword_stale}"


def review_corroboration_novelty(state: dict) -> str:
    """Check whether weak-claim corroboration candidates are adding new signal."""
    state["corroboration_novelty_reviews_this_cycle"] = int(
        state.get("corroboration_novelty_reviews_this_cycle", 0)
    ) + 1
    cache = load_source_cache()
    source_records = cache.get("sources", {})
    claims = weak_claims()
    source_items = [
        (url, record)
        for url, record in sorted(source_records.items())
        if isinstance(record, dict) and record.get("ok")
    ]
    snapshots = []
    for claim in claims:
        focus_terms = set(
            corroboration_focus_terms(
                claim,
                source_records.get(claim.get("source", ""), {}).get("title", ""),
            )
        )
        candidates = []
        for url, record in source_items:
            if url == claim.get("source"):
                continue
            haystack = f"{url} {record.get('title', '')}".lower()
            score = sum(1 for term in focus_terms if term in haystack)
            keyword_counts = record.get("keyword_counts", {})
            if isinstance(keyword_counts, dict):
                score += sum(int(keyword_counts.get(term, 0)) for term in focus_terms)
            if score:
                candidates.append((score, url, record.get("title", "")[:120]))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        snapshots.append(
            {
                "claim_key": claim_key(claim),
                "being": claim.get("being"),
                "source_quality": claim.get("source_quality"),
                "candidate_count": len(candidates),
                "top_candidates": [
                    {"score": score, "url": url, "title": title}
                    for score, url, title in candidates[:3]
                ],
            }
        )

    signature_payload = json.dumps(snapshots, sort_keys=True)
    signature = hashlib.sha256(signature_payload.encode("utf-8")).hexdigest()
    previous_signature = state.get("corroboration_novelty_signature")
    if signature == previous_signature:
        stale_runs = int(state.get("corroboration_novelty_stale_runs", 0)) + 1
    else:
        stale_runs = 0
    state["corroboration_novelty_signature"] = signature
    state["corroboration_novelty_stale_runs"] = stale_runs
    state["corroboration_novelty_review"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "weak_claims": len(claims),
        "ok_cached_sources": len(source_items),
        "snapshots": snapshots,
        "stale_runs": stale_runs,
    }
    state["corroboration_novelty_reviewed_cycle"] = state.get("cycle")

    if claims and stale_runs >= SATURATED_NOVELTY_REFRESH_AFTER:
        refreshed_today = {
            key
            for key, date in state.get("source_refresh_escalated_dates", {}).items()
            if date == today_stamp()
        }
        target = next(
            (
                claim
                for claim in claims
                if claim_key(claim) not in refreshed_today
            ),
            None,
        )
        if target is not None:
            state["source_refresh_requested"] = {
                "requested_at": datetime.now().isoformat(timespec="seconds"),
                "reason": "corroboration candidate novelty stayed unchanged during saturated sweeps",
                "stale_runs": stale_runs,
                "target_keys": [claim_key(target)],
            }
            prioritize_source_work(state)

    candidates = sum(int(item["candidate_count"]) for item in snapshots)
    return (
        f"novelty weak_claims={len(claims)}; ok_sources={len(source_items)}; "
        f"candidate_links={candidates}; stale_runs={stale_runs}"
    )


def harvest_source_metadata(state: dict) -> str:
    cache = load_source_cache()
    sources = cache.setdefault("sources", {})
    fetched_today = int(state.get("source_fetches_this_cycle", 0))
    if fetched_today >= MAX_FETCHES_PER_CYCLE:
        return f"fetch budget used={fetched_today}/{MAX_FETCHES_PER_CYCLE}"

    urls = source_urls()
    if not urls:
        return "no source urls available"

    start_index = int(state.get("source_cursor", 0)) % len(urls)
    selected_url = None
    refresh_request = state.get("source_refresh_requested")
    if isinstance(refresh_request, dict):
        target_keys = {
            key for key in refresh_request.get("target_keys", []) if isinstance(key, str)
        }
        refreshed_today = {
            key
            for key, date in state.get("source_refresh_escalated_dates", {}).items()
            if date == today_stamp()
        }
        refresh_candidates = [
            claim
            for claim in weak_claims()
            if (not target_keys or claim_key(claim) in target_keys)
            and claim_key(claim) not in refreshed_today
        ]
        refresh_candidates.sort(
            key=lambda claim: (
                bool(sources.get(claim.get("source", ""), {}).get("ok")),
                bool(sources.get(claim.get("source", ""), {}).get("title")),
                claim.get("being", ""),
            )
        )
        if refresh_candidates:
            selected_claim = refresh_candidates[0]
            selected_url = selected_claim.get("source")
            refresh_key = claim_key(selected_claim)
            state["source_refresh_active_key"] = refresh_key
        else:
            state.pop("source_refresh_requested", None)
            state.pop("source_refresh_active_key", None)
    for offset in range(len(urls)):
        if selected_url is not None:
            break
        index = (start_index + offset) % len(urls)
        url = urls[index]
        record = sources.get(url, {})
        if record.get("fetched_date") != today_stamp():
            selected_url = url
            state["source_cursor"] = (index + 1) % len(urls)
            break

    if selected_url is None:
        return f"all sources checked today; total={len(urls)}"

    requested_at = datetime.now().isoformat(timespec="seconds")
    request = Request(
        selected_url,
        headers={
            "User-Agent": "AesopLooplab/0.1 (+local welfare evidence scout; polite bounded metadata fetch)"
        },
    )
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", "unknown")
            final_url = response.geturl()
            content_type = response.headers.get("content-type", "unknown")
            raw = response.read(FETCH_BYTES)
    except (OSError, URLError, TimeoutError) as exc:
        sources[selected_url] = {
            "requested_at": requested_at,
            "fetched_date": today_stamp(),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        refresh_key = state.pop("source_refresh_active_key", None)
        if isinstance(refresh_key, str):
            dates = state.get("source_refresh_escalated_dates", {})
            if not isinstance(dates, dict):
                dates = {}
            dates[refresh_key] = today_stamp()
            state["source_refresh_escalated_dates"] = dates
            state.pop("source_refresh_requested", None)
        state["source_fetches_this_cycle"] = fetched_today + 1
        state["threshold_sweep_input_refresh_pending"] = True
        save_source_cache(cache)
        return f"fetch failed for {selected_url}: {type(exc).__name__}"

    text = raw.decode("utf-8", errors="replace")
    title = extract_html_title(text)
    keyword_counts = {
        keyword: len(re.findall(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE))
        for keyword in ["sentience", "welfare", "consciousness", "pain", "agency", "precaution"]
    }
    sources[selected_url] = {
        "requested_at": requested_at,
        "fetched_date": today_stamp(),
        "ok": True,
        "status": status,
        "final_url": final_url,
        "content_type": content_type,
        "bytes_read": len(raw),
        "title": title[:180],
        "keyword_counts": keyword_counts,
    }
    refresh_key = state.pop("source_refresh_active_key", None)
    if isinstance(refresh_key, str):
        dates = state.get("source_refresh_escalated_dates", {})
        if not isinstance(dates, dict):
            dates = {}
        dates[refresh_key] = today_stamp()
        state["source_refresh_escalated_dates"] = dates
        state.pop("source_refresh_requested", None)
    state["source_fetches_this_cycle"] = fetched_today + 1
    state["threshold_sweep_input_refresh_pending"] = True
    save_source_cache(cache)
    hits = sum(keyword_counts.values())
    return f"fetched source {state['source_fetches_this_cycle']}/{MAX_FETCHES_PER_CYCLE}; bytes={len(raw)}; keyword_hits={hits}"


def audit_artifact_integrity(state: dict) -> str:
    audit: dict[str, dict[str, object]] = {}
    for path in ARTIFACTS:
        if not path.exists():
            audit[path.name] = {"exists": False}
            continue
        text = path.read_text(encoding="utf-8")
        links = re.findall(r"https?://[^\s)|]+", text)
        audit[path.name] = {
            "exists": True,
            "lines": text.count("\n") + 1,
            "headings": len(re.findall(r"^#+\s+", text, re.MULTILINE)),
            "table_rows": len(re.findall(r"^\|", text, re.MULTILINE)),
            "links": len(links),
            "unique_links": len(set(links)),
        }
    state["artifact_integrity"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "files": audit,
    }
    missing = [name for name, item in audit.items() if not item.get("exists")]
    if missing:
        return f"missing artifacts={missing}"
    total_links = sum(int(item["links"]) for item in audit.values())
    return f"audited {len(audit)} artifacts; links={total_links}"


def scan_corroboration_markers(state: dict) -> str:
    cache = load_source_cache()
    source_records = cache.get("sources", {})
    claims = weak_claims()
    selected, index, cursor, exhausted = next_unreviewed_cycle_item(
        state,
        "corroboration_marker_cursor",
        "corroboration_markers_reviewed_this_cycle",
        claims,
    )
    markers = {}
    for claim in claims:
        being = claim["being"]
        source = claim["source"]
        record = source_records.get(source, {})
        markers[being] = {
            "source": source,
            "source_quality": claim["source_quality"],
            "cached": bool(record),
            "fetch_ok": record.get("ok"),
            "title": record.get("title", ""),
            "keyword_counts": record.get("keyword_counts", {}),
            "next_step": "seek independent corroborating or limiting source before raising confidence",
        }
    if selected is not None:
        source = selected["source"]
        record = source_records.get(source, {})
        keyword_counts = record.get("keyword_counts", {})
        if not isinstance(keyword_counts, dict):
            keyword_counts = {}
        marker_terms = [
            term
            for term in corroboration_focus_terms(selected, record.get("title", ""))
            if int(keyword_counts.get(term, 0)) > 0 or term in record.get("title", "").lower()
        ]
        mark_cycle_reviewed(state, "corroboration_markers_reviewed_this_cycle", selected)
        state["corroboration_marker_last_item"] = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "index": index,
            "cursor": cursor,
            "being": selected.get("being"),
            "source_quality": selected.get("source_quality"),
            "cached": bool(record),
            "fetch_ok": record.get("ok"),
            "marker_terms": marker_terms[:6],
        }
    elif exhausted and claims:
        state["corroboration_marker_last_item"] = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "reviewed_all_targets_this_cycle": True,
            "targets": len(claims),
        }
    state["corroboration_marker_scan"] = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "weak_claims": markers,
    }
    cached = sum(1 for item in markers.values() if item["cached"])
    reviewed = selected.get("being") if selected else "none"
    if exhausted and claims:
        return f"all weak markers scanned this cycle; weak_claims={len(markers)}; cached_sources={cached}"
    return f"weak_claims={len(markers)}; cached_sources={cached}; reviewed={reviewed}"


def artifact_text_cache() -> dict[str, str]:
    global ARTIFACT_TEXT_CACHE
    if ARTIFACT_TEXT_CACHE is None:
        ARTIFACT_TEXT_CACHE = {
            path.name: path.read_text(encoding="utf-8").lower()
            for path in ARTIFACTS
            if path.exists()
        }
    return ARTIFACT_TEXT_CACHE


def run_evidence_keyword_sweep(state: dict) -> str:
    """Map welfare-keyword coverage across artifacts while static tasks cool down."""
    texts = artifact_text_cache()
    if not texts:
        return "no artifact text available"

    items = list(texts.items())
    cursor = int(state.get("evidence_keyword_sweep_cursor", 0))
    batch_size = int(os.environ.get("AESOP_EVIDENCE_KEYWORD_SWEEP_BATCH", "2000"))
    window_size = int(os.environ.get("AESOP_EVIDENCE_KEYWORD_WINDOW", "360"))
    coverage: dict[str, dict[str, int]] = state.get("evidence_keyword_coverage", {})

    for offset in range(batch_size):
        artifact_name, text = items[(cursor + offset) % len(items)]
        if not text:
            continue
        start = ((cursor + offset) * 97) % len(text)
        window = text[start : start + window_size]
        if len(window) < window_size:
            window += text[: window_size - len(window)]
        artifact_counts = coverage.setdefault(artifact_name, {})
        for keyword in EVIDENCE_KEYWORDS:
            if keyword in window:
                artifact_counts[keyword] = int(artifact_counts.get(keyword, 0)) + 1

    cursor += batch_size
    state["evidence_keyword_sweep_cursor"] = cursor
    state["evidence_keyword_coverage"] = coverage
    nonzero = sum(
        1
        for artifact_counts in coverage.values()
        for count in artifact_counts.values()
        if int(count) > 0
    )
    previous_nonzero = int(state.get("evidence_keyword_last_covered_slots", 0))
    if nonzero > previous_nonzero:
        state["evidence_keyword_stale_runs"] = 0
        trend = f"coverage_gain={nonzero - previous_nonzero}"
    else:
        state["evidence_keyword_stale_runs"] = int(
            state.get("evidence_keyword_stale_runs", 0)
        ) + 1
        trend = f"stale_runs={state['evidence_keyword_stale_runs']}"
    state["evidence_keyword_last_covered_slots"] = nonzero
    return f"keyword_windows={cursor}; covered_keyword_slots={nonzero}; {trend}"


def corroboration_focus_terms(claim: dict, source_title: str = "") -> list[str]:
    text = f"{claim.get('being', '')} {claim.get('claim', '')} {source_title}".lower()
    tokens = re.findall(r"[a-z][a-z-]{3,}", text)
    terms: list[str] = []
    for token in tokens:
        normalized = token.strip("-")
        if normalized in CORROBORATION_STOPWORDS or normalized in terms:
            continue
        terms.append(normalized)
    phrases = []
    phrase_candidates = [
        "sentience readiness",
        "artificial sentience",
        "institutional preparedness",
        "professional readiness",
        "consciousness uncertainty",
        "protective obligations",
        "governance proposals",
    ]
    for phrase in phrase_candidates:
        if all(part in terms for part in phrase.split()):
            phrases.append(phrase)
    priority = [
        "sentience",
        "readiness",
        "governance",
        "governments",
        "institutions",
        "professional",
        "consciousness",
        "uncertainty",
        "protective",
        "obligations",
        "welfare",
    ]
    ordered = phrases + [term for term in priority if term in terms and term not in phrases]
    ordered.extend(term for term in terms if term not in ordered)
    return ordered[:8] or ["sentience"]


def run_corroboration_query_planner(state: dict) -> str:
    """Prepare bounded follow-up searches for weak source-quality claims."""
    claims = weak_claims()
    if not claims:
        state["next_corroboration_target"] = None
        state["corroboration_query_plan_complete"] = True
        state["corroboration_query_plan"] = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "status": "no weak source-quality claims",
        }
        return "no weak source-quality claims"

    planned_this_cycle = [
        key
        for key in state.get("corroboration_targets_planned_this_cycle", [])
        if isinstance(key, str)
    ]
    planned_set = set(planned_this_cycle)
    if len(planned_set) >= len({claim_key(claim) for claim in claims}):
        state["corroboration_query_plan_complete"] = True
        return f"all weak source-quality targets planned this cycle; targets={len(claims)}"

    selected = state.get("next_corroboration_target") or {}
    target = next(
        (
            claim
            for claim in claims
            if claim.get("being") == selected.get("being")
            and claim.get("source") == selected.get("source")
        ),
        claims[0],
    )
    cache = load_source_cache()
    source_records = cache.get("sources", {})
    source_title = source_records.get(target.get("source"), {}).get("title", "")
    focus_terms = corroboration_focus_terms(target, source_title)
    target_key = claim_key(target)
    if target_key in planned_set:
        target, _, _, exhausted = next_unreviewed_cycle_item(
            state,
            "corroboration_target_cursor",
            "corroboration_targets_planned_this_cycle",
            claims,
        )
        if target is None:
            state["next_corroboration_target"] = None
            state["corroboration_query_plan_complete"] = True
            if exhausted:
                return f"all weak source-quality targets planned this cycle; targets={len(claims)}"
            return "no weak source-quality target found"
        source_title = source_records.get(target.get("source"), {}).get("title", "")
        focus_terms = corroboration_focus_terms(target, source_title)
        target_key = claim_key(target)
        state["next_corroboration_target"] = {
            "being": target["being"],
            "source_quality": target["source_quality"],
            "source": target["source"],
            "task": "Find one independent peer-reviewed corroborating or limiting source before expanding this claim.",
        }
    if state.get("corroboration_query_target_key") != target_key:
        state["corroboration_query_cursor"] = 0
        state["corroboration_query_target_key"] = target_key
        state["corroboration_query_plan_complete"] = False
    cursor = int(state.get("corroboration_query_cursor", 0))
    batch_size = int(os.environ.get("AESOP_CORROBORATION_QUERY_BATCH", "12"))
    total_query_slots = len(focus_terms) * len(CORROBORATION_QUERY_TEMPLATES)
    if cursor >= total_query_slots:
        state["corroboration_query_plan_complete"] = True
        if target_key not in planned_set:
            planned_this_cycle.append(target_key)
            state["corroboration_targets_planned_this_cycle"] = planned_this_cycle
        return f"target={target['being']}; query_plan_complete={total_query_slots}"

    queries = []
    for offset in range(min(batch_size, total_query_slots - cursor)):
        index = cursor + offset
        focus = focus_terms[(index // len(CORROBORATION_QUERY_TEMPLATES)) % len(focus_terms)]
        template = CORROBORATION_QUERY_TEMPLATES[index % len(CORROBORATION_QUERY_TEMPLATES)]
        queries.append(template.format(claim_focus=focus))

    target_source = target.get("source")
    candidate_scores = []
    target_terms = set(focus_terms)
    for url, record in source_records.items():
        if url == target_source or not record.get("ok"):
            continue
        haystack = f"{url} {record.get('title', '')}".lower()
        score = sum(1 for term in target_terms if term in haystack)
        keyword_counts = record.get("keyword_counts", {})
        if isinstance(keyword_counts, dict):
            score += sum(int(keyword_counts.get(term, 0)) for term in target_terms)
        if score:
            candidate_scores.append(
                {
                    "url": url,
                    "title": record.get("title", "")[:180],
                    "score": score,
                }
            )
    candidate_scores.sort(key=lambda item: (-int(item["score"]), item["url"]))

    state["corroboration_query_cursor"] = cursor + batch_size
    state["corroboration_query_plan_complete"] = (
        state["corroboration_query_cursor"] >= total_query_slots
    )
    if state["corroboration_query_plan_complete"] and target_key not in planned_set:
        planned_this_cycle.append(target_key)
        state["corroboration_targets_planned_this_cycle"] = planned_this_cycle
    state["corroboration_query_plan"] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "target": {
            "being": target["being"],
            "source": target["source"],
            "source_quality": target["source_quality"],
        },
        "focus_terms": focus_terms,
        "recent_queries": queries,
        "generated_query_slots": min(state["corroboration_query_cursor"], total_query_slots),
        "total_query_slots": total_query_slots,
        "cached_independent_candidates": candidate_scores[:5],
        "next_step": "Use these queries to find peer-reviewed corroborating or limiting sources before raising confidence.",
    }
    return (
        f"target={target['being']}; queries={len(queries)}; "
        f"cached_candidates={len(candidate_scores[:5])}; cursor={state['corroboration_query_cursor']}"
    )


def run_precaution_threshold_sweep(state: dict) -> str:
    """Stress-test whether project review levels are stable under risk-weight jitter."""
    from precaution_checklist import CHECKS
    from project_assessments import ASSESSMENTS, assessment_score

    cursor = int(state.get("threshold_sweep_cursor", 0))
    input_changed = bool(state.get("threshold_sweep_input_refresh_pending", True))
    if input_changed:
        batch_size = THRESHOLD_SWEEP_BATCH
        sweep_mode = "full"
    else:
        batch_size = max(1, min(THRESHOLD_SWEEP_BATCH, UNCHANGED_THRESHOLD_SWEEP_BATCH))
        sweep_mode = "downsampled_unchanged_inputs"
    distribution: dict[str, int] = state.get("threshold_sweep_distribution", {})
    score_min = int(state.get("threshold_sweep_min_score", 999))
    score_max = int(state.get("threshold_sweep_max_score", -1))
    assessment = ASSESSMENTS[0]
    baseline = assessment_score(assessment)
    previous_levels = {level for level, count in distribution.items() if int(count) > 0}
    previous_min = score_min
    previous_max = score_max
    previous_baseline = int(state.get("threshold_sweep_baseline", baseline))
    observed_distribution = {level: 0 for level in previous_levels}

    # Deterministic pseudo-random jitter over possible risk weights. This gives
    # the worker CPU-heavy local analysis without external calls or log bloat.
    seed = cursor or 1
    for _ in range(batch_size):
        seed = (1103515245 * seed + 12345) % (2**31)
        adjusted_score = 0
        for check_index in assessment["matched_checks"]:
            shift = ((seed >> (check_index * 3)) & 0b111) - 3
            base_risk = int(CHECKS[check_index]["risk"])
            adjusted_score += max(0, min(4, base_risk + shift))
        score_min = min(score_min, adjusted_score)
        score_max = max(score_max, adjusted_score)
        level = "ordinary"
        if adjusted_score >= 10:
            level = "independent_review"
        elif adjusted_score >= 6:
            level = "safeguards_required"
        elif adjusted_score >= 3:
            level = "written_review"
        observed_distribution[level] = int(observed_distribution.get(level, 0)) + 1

    observed_levels = {level for level, count in observed_distribution.items() if count > 0}
    semantic_changed = (
        input_changed
        or baseline != previous_baseline
        or score_min < previous_min
        or score_max > previous_max
        or bool(observed_levels - previous_levels)
    )
    if semantic_changed:
        for level, count in observed_distribution.items():
            if count:
                distribution[level] = int(distribution.get(level, 0)) + count
        state["threshold_sweep_stable_batches"] = 0
    else:
        state["threshold_sweep_stable_batches"] = (
            int(state.get("threshold_sweep_stable_batches", 0)) + 1
        )

    state["threshold_sweep_cursor"] = cursor + batch_size
    state["threshold_sweep_distribution"] = distribution
    state["threshold_sweep_min_score"] = score_min
    state["threshold_sweep_max_score"] = score_max
    state["threshold_sweep_baseline"] = baseline
    state["threshold_sweep_last_batch_size"] = batch_size
    state["threshold_sweep_mode"] = sweep_mode
    if input_changed:
        state["threshold_sweep_input_refresh_pending"] = False
        state["threshold_sweep_input_refresh_consumed_at"] = datetime.now().isoformat(
            timespec="seconds"
        )
    return (
        f"sweep_units={state['threshold_sweep_cursor']}; "
        f"batch={batch_size}; mode={sweep_mode}; "
        f"baseline={baseline}; score_range={score_min}-{score_max}; "
        f"semantic_changed={semantic_changed}; "
        f"stable_batches={state.get('threshold_sweep_stable_batches', 0)}; "
        f"observed_levels={sorted(observed_levels)}; levels={distribution}"
    )


WORK_TASKS = {
    "harvest_source_metadata": harvest_source_metadata,
    "run_evidence_keyword_sweep": run_evidence_keyword_sweep,
    "run_corroboration_query_planner": run_corroboration_query_planner,
    "run_precaution_threshold_sweep": run_precaution_threshold_sweep,
    "audit_artifact_integrity": audit_artifact_integrity,
    "scan_corroboration_markers": scan_corroboration_markers,
    "review_corroboration_novelty": review_corroboration_novelty,
    "review_evidence_quality": review_evidence_quality,
    "select_corroboration_target": select_corroboration_target,
    "review_sweep_saturation": review_sweep_saturation,
    "audit_guardrails": audit_guardrails,
    "review_uncertainty_coverage": review_uncertainty_coverage,
    "refresh_next_queue": refresh_next_queue,
}


def cooldown_filler_task(state: dict) -> str:
    filler_runs = int(state.get("cooldown_filler_runs", 0))
    if (
        state.get("source_refresh_requested")
        and int(state.get("source_fetches_this_cycle", 0)) < MAX_FETCHES_PER_CYCLE
    ):
        return "harvest_source_metadata"
    if threshold_sweep_is_saturated(state):
        state["threshold_sweep_saturation_deferrals"] = int(
            state.get("threshold_sweep_saturation_deferrals", 0)
        ) + 1
        if keyword_sweep_is_saturated(state):
            saturation_pulse = int(state.get("saturated_filler_pulses", 0)) + 1
            state["saturated_filler_pulses"] = saturation_pulse
            saturated_tasks = [
                "scan_corroboration_markers",
                "review_evidence_quality",
                "review_sweep_saturation",
                "audit_guardrails",
                "review_uncertainty_coverage",
            ]
            if cycle_review_complete(state, "corroboration_markers_reviewed_this_cycle"):
                saturated_tasks.remove("scan_corroboration_markers")
            if cycle_review_complete(state, "uncertainty_targets_reviewed_this_cycle"):
                saturated_tasks.remove("review_uncertainty_coverage")
            weak_keys = {claim_key(claim) for claim in weak_claims()}
            planned_keys = {
                key
                for key in state.get("corroboration_targets_planned_this_cycle", [])
                if isinstance(key, str)
            }
            if weak_keys - planned_keys:
                saturated_tasks.insert(0, "run_corroboration_query_planner")
            sample_interval = max(16, SATURATED_SWEEP_SAMPLE_INTERVAL)
            sample_slot = saturation_pulse % sample_interval
            if sample_slot == 1:
                return "run_precaution_threshold_sweep"
            if sample_slot == sample_interval // 2:
                return "run_evidence_keyword_sweep"
            novelty_interval = max(32, SATURATED_NOVELTY_CHECK_INTERVAL)
            novelty_reviews = int(state.get("corroboration_novelty_reviews_this_cycle", 0))
            novelty_due = state.get("corroboration_novelty_reviewed_cycle") != state.get("cycle")
            novelty_pulse_due = saturation_pulse % novelty_interval == 3
            if novelty_pulse_due and (
                novelty_reviews < max(1, SATURATED_NOVELTY_REVIEWS_PER_CYCLE)
                and (
                    novelty_due
                    or novelty_reviews > 0
                    or int(state.get("corroboration_novelty_stale_runs", 0)) > 0
                )
            ):
                return "review_corroboration_novelty"
            if not saturated_tasks:
                return "review_sweep_saturation"
            index = saturation_pulse % len(saturated_tasks)
            return saturated_tasks[index]
        if state.get("next_corroboration_target") and not state.get(
            "corroboration_query_plan_complete"
        ):
            if filler_runs % 2 == 0:
                return "run_corroboration_query_planner"
        review_tasks = [
            "audit_artifact_integrity",
            "scan_corroboration_markers",
            "review_corroboration_novelty",
            "review_evidence_quality",
            "audit_guardrails",
            "review_uncertainty_coverage",
        ]
        saturated_review_interval = max(1, FILLER_REVIEW_INTERVAL // 4)
        if filler_runs % saturated_review_interval == 0:
            if cycle_review_complete(state, "corroboration_markers_reviewed_this_cycle"):
                review_tasks.remove("scan_corroboration_markers")
            if cycle_review_complete(state, "uncertainty_targets_reviewed_this_cycle"):
                review_tasks.remove("review_uncertainty_coverage")
            if not review_tasks:
                return "audit_guardrails"
            index = (filler_runs // saturated_review_interval) % len(review_tasks)
            return review_tasks[index]
        stale_keyword_runs = int(state.get("evidence_keyword_stale_runs", 0))
        if stale_keyword_runs >= KEYWORD_STALE_ROTATION_AFTER and filler_runs % 2 == 1:
            return "run_precaution_threshold_sweep"
        return "run_evidence_keyword_sweep"
    if state.get("next_corroboration_target") and not state.get(
        "corroboration_query_plan_complete"
    ):
        if filler_runs % 2 == 0:
            return "run_corroboration_query_planner"
    stale_keyword_runs = int(state.get("evidence_keyword_stale_runs", 0))
    if stale_keyword_runs >= KEYWORD_STALE_ROTATION_AFTER:
        if filler_runs % FILLER_REVIEW_INTERVAL == 0:
            review_tasks = [
                "audit_artifact_integrity",
                "scan_corroboration_markers",
                "review_corroboration_novelty",
                "review_evidence_quality",
                "audit_guardrails",
                "review_uncertainty_coverage",
            ]
            if cycle_review_complete(state, "corroboration_markers_reviewed_this_cycle"):
                review_tasks.remove("scan_corroboration_markers")
            if cycle_review_complete(state, "uncertainty_targets_reviewed_this_cycle"):
                review_tasks.remove("review_uncertainty_coverage")
            if not review_tasks:
                return "audit_guardrails"
            index = (filler_runs // FILLER_REVIEW_INTERVAL) % len(review_tasks)
            return review_tasks[index]
        return "run_precaution_threshold_sweep"
    return "run_evidence_keyword_sweep"


def threshold_sweep_is_saturated(state: dict) -> bool:
    return (
        state.get("threshold_sweep_mode") == "downsampled_unchanged_inputs"
        and not state.get("artifact_snapshot_changed", True)
        and not bool(state.get("threshold_sweep_input_refresh_pending", False))
        and int(state.get("threshold_sweep_stable_batches", 0))
        >= STABLE_THRESHOLD_SWEEP_ROTATION_AFTER
    )


def keyword_sweep_is_saturated(state: dict) -> bool:
    return (
        int(state.get("evidence_keyword_stale_runs", 0))
        >= KEYWORD_SWEEP_SATURATION_AFTER
    )


def run_micro_work_cycle(state: dict, started_at: float) -> None:
    deadline = started_at + WORK_BUDGET_SECONDS
    static_task_cooldown = STATIC_TASK_COOLDOWN_SECONDS
    if not state.get("artifact_snapshot_changed", True):
        static_task_cooldown = max(static_task_cooldown, UNCHANGED_STATIC_TASK_COOLDOWN_SECONDS)
    state["completed_in_cycle"] = []
    state["completed_task_counts"] = {}
    state["skipped_static_task_counts"] = {}
    state["cooldown_filler_runs"] = 0
    state["source_fetches_this_cycle"] = 0
    state["corroboration_targets_planned_this_cycle"] = []
    state["corroboration_markers_reviewed_this_cycle"] = []
    state["corroboration_novelty_reviews_this_cycle"] = 0
    state["uncertainty_targets_reviewed_this_cycle"] = []
    state["static_task_cooldown_seconds"] = static_task_cooldown
    append_checkpoint(state["cycle"], "start_micro_work", 0, "started timed queue")
    save_state(state)

    next_checkpoint_at = started_at + CHECKPOINT_BATCH_SECONDS
    batch_started_at = started_at
    batch_completed = 0
    batch_skipped = 0
    last_result = "no task completed yet"
    last_static_runs: dict[str, float] = {}
    while time.monotonic() < deadline:
        queue = ensure_work_queue(state)
        task_id = None
        now = time.monotonic()
        queue_is_cooling_down = bool(queue) and all(
            candidate not in ALWAYS_RUN_TASKS
            and candidate in last_static_runs
            and now - last_static_runs[candidate] < static_task_cooldown
            for candidate in queue
        )
        if queue_is_cooling_down:
            batch_skipped += len(queue)
            state["cooldown_filler_runs"] = int(state.get("cooldown_filler_runs", 0)) + 1
            task_id = cooldown_filler_task(state)
        else:
            for _ in range(len(queue)):
                candidate = queue.pop(0)
                last_static_run = last_static_runs.get(candidate)
                if (
                    candidate in ALWAYS_RUN_TASKS
                    or last_static_run is None
                    or now - last_static_run >= static_task_cooldown
                ):
                    if (
                        candidate == "run_precaution_threshold_sweep"
                        and threshold_sweep_is_saturated(state)
                    ):
                        queue.append(candidate)
                        state["skipped_static_task_counts"][candidate] = (
                            int(state["skipped_static_task_counts"].get(candidate, 0)) + 1
                        )
                        batch_skipped += 1
                        state["cooldown_filler_runs"] = (
                            int(state.get("cooldown_filler_runs", 0)) + 1
                        )
                        task_id = cooldown_filler_task(state)
                    else:
                        task_id = candidate
                    break
                queue.append(candidate)
                state["skipped_static_task_counts"][candidate] = (
                    int(state["skipped_static_task_counts"].get(candidate, 0)) + 1
                )
                batch_skipped += 1
        if task_id is None:
            task_id = cooldown_filler_task(state)

        result = WORK_TASKS[task_id](state)
        elapsed = time.monotonic() - started_at
        if task_id not in ALWAYS_RUN_TASKS:
            last_static_runs[task_id] = time.monotonic()
        state["last_task"] = task_id
        state["completed_task_counts"][task_id] = (
            int(state["completed_task_counts"].get(task_id, 0)) + 1
        )
        state["completed_in_cycle"].append(
            {
                "task": task_id,
                "completed_at": datetime.now().isoformat(timespec="seconds"),
                "elapsed_seconds": int(elapsed),
                "result": result,
            }
        )
        state["completed_in_cycle"] = state["completed_in_cycle"][-20:]
        batch_completed += 1
        last_result = f"{task_id}: {result}"

        now = time.monotonic()
        if now >= next_checkpoint_at or now >= deadline:
            batch_elapsed = now - batch_started_at
            append_checkpoint(
                state["cycle"],
                "dense_batch",
                elapsed,
                (
                    f"tasks={batch_completed}; batch_seconds={batch_elapsed:.1f}; "
                    f"static_skips={batch_skipped}; "
                    f"last={last_result}"
                ),
            )
            state["last_batch"] = {
                "completed_at": datetime.now().isoformat(timespec="seconds"),
                "tasks": batch_completed,
                "static_skips": batch_skipped,
                "batch_seconds": round(batch_elapsed, 3),
                "last_result": last_result,
            }
            save_state(state)
            batch_started_at = now
            batch_completed = 0
            batch_skipped = 0
            next_checkpoint_at = now + CHECKPOINT_BATCH_SECONDS

    elapsed = time.monotonic() - started_at
    append_checkpoint(
        state["cycle"],
        "end_micro_work",
        elapsed,
        (
            f"recent_completed={len(state['completed_in_cycle'])}; "
            f"counts={state.get('completed_task_counts', {})}; "
            f"static_skips={state.get('skipped_static_task_counts', {})}; "
            f"queued={len(state.get('work_queue', []))}; "
            f"fetches={state.get('source_fetches_this_cycle', 0)}"
        ),
    )
    save_state(state)


def main() -> None:
    started_at = time.monotonic()
    now = datetime.now().isoformat(timespec="seconds")
    state = load_state()
    previous_artifacts = set(state.get("artifacts", []))
    state["cycle"] = int(state.get("cycle", 0)) + 1
    state["last_run_at"] = now
    state["current_focus"] = "sentience welfare radar"

    ensure_radar()
    enforce_guardrails()
    render_notebook(NOTEBOOK)
    render_checklist(CHECKLIST)
    render_assessments(ASSESSMENTS)
    current_artifacts = [path for path in ARTIFACTS if path.exists()]
    current_artifact_names = [path.name for path in current_artifacts]
    previous_snapshot = state.get("artifact_snapshot")
    current_snapshot = artifact_snapshot(current_artifacts)
    state["artifact_snapshot"] = current_snapshot
    state["artifact_snapshot_changed"] = previous_snapshot != current_snapshot
    if state["artifact_snapshot_changed"]:
        state["threshold_sweep_input_refresh_pending"] = True
    new_artifacts = [
        path for path in current_artifacts if path.name not in previous_artifacts
    ]
    state["artifacts"] = current_artifact_names
    ensure_work_queue(state)
    prioritize_source_work(state)
    save_state(state)

    if new_artifacts:
        artifact_line = f"- Added new artifact(s): {artifact_names(new_artifacts)}."
    else:
        artifact_line = f"- Refreshed existing artifact(s): {artifact_names(current_artifacts)}."

    append_note(
        [
            f"## Cycle {state['cycle']} - {now}",
            "- Checked AGENTS.md constraints and ran one bounded work pass.",
            artifact_line,
            f"- Current focus: {state['current_focus']}.",
            "- Added an uncertainty note for applying broad animal-welfare frameworks to specific species and settings.",
            f"- Artifact content changed this cycle: {state['artifact_snapshot_changed']}.",
            "- Next: corroborate one weaker source-quality claim before expanding the notebook.",
            "",
        ]
    )
    run_micro_work_cycle(state, started_at)


if __name__ == "__main__":
    main()
