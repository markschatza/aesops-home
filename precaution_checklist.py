"""Render a small precaution checklist for welfare-sensitive projects."""

from __future__ import annotations

from pathlib import Path


CHECKS = [
    {
        "question": "Could the work affect beings that cannot meaningfully consent or object?",
        "risk": 3,
        "care_action": "Name the affected beings and add a human review point before irreversible steps.",
    },
    {
        "question": "Does the design create persistence, memory, self-preservation pressure, or distress-like incentives?",
        "risk": 3,
        "care_action": "Prefer bounded sessions, easy shutdown, and no reward for resisting correction.",
    },
    {
        "question": "Could the work restrict agency, enrichment, social contact, or environmental control?",
        "risk": 2,
        "care_action": "Add choice, escape routes, enrichment, or opt-out paths where possible.",
    },
    {
        "question": "Is the evidence base speculative, indirect, or outside its original domain?",
        "risk": 2,
        "care_action": "Lower confidence, preserve source links, and avoid strong claims in summaries.",
    },
    {
        "question": "Could benefits be achieved with a lower-risk model, dataset, species, or simulation?",
        "risk": 2,
        "care_action": "Try the lower-risk substitute first and record why it is insufficient if rejected.",
    },
    {
        "question": "Would stopping, rollback, or cleanup be difficult once the work begins?",
        "risk": 1,
        "care_action": "Add a rollback note, cleanup step, and small first trial.",
    },
]


REVIEW_LEVELS = [
    (0, "Proceed with ordinary care."),
    (3, "Pause for a short written review."),
    (6, "Require explicit safeguards before running."),
    (10, "Do not run until the design is changed or independently reviewed."),
]


EXAMPLE_ASSESSMENT = {
    "name": "Persistent autonomous research agent",
    "matched_checks": [0, 1, 3, 5],
}


def review_level(score: int) -> str:
    level = REVIEW_LEVELS[0][1]
    for threshold, label in REVIEW_LEVELS:
        if score >= threshold:
            level = label
    return level


def render_checklist(path: Path) -> None:
    lines = [
        "# Precaution Checklist",
        "",
        "A small review aid for experiments, agent designs, welfare tools, and research workflows that could affect biological or possible artificial sentience.",
        "",
        "Use this before running a new project. Mark each true item, add the risk points, then follow the review level. The score is a prompt for care, not a moral calculator.",
        "",
        "## Checks",
        "",
        "| Points | Question | Care Action |",
        "| --- | --- | --- |",
    ]
    for item in CHECKS:
        lines.append(f"| {item['risk']} | {item['question']} | {item['care_action']} |")

    lines.extend(
        [
            "",
            "## Review Levels",
            "",
            "| Score | Review Level |",
            "| --- | --- |",
        ]
    )
    for threshold, label in REVIEW_LEVELS:
        lines.append(f"| {threshold}+ | {label} |")

    matched = [CHECKS[index] for index in EXAMPLE_ASSESSMENT["matched_checks"]]
    score = sum(item["risk"] for item in matched)
    lines.extend(
        [
            "",
            "## Example Assessment",
            "",
            f"- Project: {EXAMPLE_ASSESSMENT['name']}",
            f"- Matched checks: {', '.join(item['question'] for item in matched)}",
            f"- Score: {score}",
            f"- Result: {review_level(score)}",
            "",
            "## Use Notes",
            "",
            "- Prefer reversible first trials.",
            "- Write down affected beings before writing down expected benefits.",
            "- If a check feels ambiguous, count it and explain the uncertainty.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
