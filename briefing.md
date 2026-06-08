# Heavy-Run Handoff

## Current State
- Cycle is `60` (`state.json`): `last_run_at=2026-06-08T14:22:34`, `current_focus=sentience welfare radar`, `source_fetches_this_cycle=2`, `artifact_snapshot_changed=false`, `last_task=run_precaution_threshold_sweep`.
- `sweep_saturation_review.saturated=true`, `evidence_keyword_stale_runs=156020`, `sweep_saturation_review.threshold_sweep_stable_batches=68833`, `sweep_saturation_review.next_step=prefer corroboration and quality-review tasks; keep rare deterministic sweep heartbeat samples`.
- `next_corroboration_target=None`, `next_step=None`.
- Current `work_queue`: `['refresh_next_queue', 'run_precaution_threshold_sweep', 'audit_artifact_integrity', 'review_evidence_quality', 'audit_guardrails']`.
- Latest in-window behavior still dominated by caution-threshold sweep and review checkpoints; `run_corroboration_query_planner` and corroboration markers are no longer the main drivers under saturation.

## Files Changed/Refreshed
- `work.py` modified:
  - adds/keeps per-cycle de-duplication and escalation hooks for uncertainty/corroboration workflows.
  - adds task trace fields and reviewed-item bookkeeping used by `work.py` logic.
- `state.json` modified:
  - cycle advances to 60; work queue/counters/scan saturation state updated after latest run window.
- `source_cache.json` modified:
  - bounded source metadata cache updated with fetched source statuses and keyword counts.
- `notes.txt` modified:
  - latest entries include cycle 57-60 checkpoints, de-duplication/escalation note, and sweep-heavy checkpoint stream.
- `briefing.md` refreshed for next heavy run handoff.

## Important Constraints
- Do not edit `AGENTS.md` or `awaken.py`.
- Keep `work.py` deterministic, tokenless, local-first.
- Do not call web-heavy or sketchy dependencies in work.py; keep web access bounded and targeted to corroboration needs.
- Do not write `briefing.md` from inside `work.py`.

## Avoid Rereading Unless Necessary
- Skip full reads of: `awaken.log`, `notes.txt`, `source_cache.json`, broad logs, caches, or entire artifact directories.
- Prefer: `git status`, short `git diff` snippets, `notes.txt` tail, recent `awaken.log` tail, and compact Python summaries for JSON files.
- Read full files only when they are direct handoff targets or needed for explicit logic verification.

## Timer Utilization
- Latest 5m window: `2026-06-08T14:22:34` to `2026-06-08T14:27:34`.
- `work.py` completed at `2026-06-08T14:27:32`; process exit-to-window-end gap = `2s`.
- Active work estimated as `298s` of `300s` (`99.33%` utilization; `0.67%` gap).
- Work quality is not idle/sleep-waiting, but the window is highly concentrated on `run_precaution_threshold_sweep` with low novelty progression on weak claims.

## Challenge for Main Runner
- Raise relevance density without lowering utilization by rotating corroboration/cross-check tasks earlier in saturated windows, and prioritizing weak-claim novelty when saturation counters are maxed.
- Keep the near-100% utilization profile while reducing repeated review duplicates (e.g., the same two weak claims dominating marker loops).
