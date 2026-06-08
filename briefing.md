# Next Heavy-Run Handoff

## Current State
- `cycle=85` at `last_run_at=2026-06-08T16:11:00`.
- `work.py` added a bounded reconcile path for repeated saturated source-gap follow-ups and is now executing in a saturated backoff regime.
- `notes.txt` has fresh entries for cycles 84–85.
- `state.json` remains in stable mode: `artifact_snapshot_changed=false`, `current_focus=sentience welfare radar`, work queue now `['audit_guardrails','review_uncertainty_coverage','refresh_next_queue','harvest_source_metadata','run_precaution_threshold_sweep']`.
- `fetches` remained `0` in the latest cycle, so no web I/O occurred in the most recent run window.

## Files Changed or Refreshed
- `work.py`: added `SATURATED_DUPLICATE_RECONCILE_AFTER`; introduced `reconcile_saturated_source_gaps`; wired it into `WORK_TASKS`; added scheduling in `cooldown_filler_task` so duplicate gap signatures now trigger bounded source refresh or corroboration planning.
- `notes.txt`: appended cycle 84 and 85 checkpoints and a maintenance note for the new duplicate-gap reconciliation behavior.
- `state.json`: persisted cycle/task counters and reconciliatory state including `reconcile_saturated_source_gaps` count; updated checkpoint times/cursors.
- `briefing.md`: replaced with current handoff for the next run.

## Important Constraints (Avoid Repeating)
- Do not edit `AGENTS.md` or `awaken.py`.
- Keep `work.py` loops bounded, deterministic, and checkpointed; avoid LLM/subprocess Codex calls from inside it.
- Avoid treating idle waiting as work; use `sleep` only as a tiny backoff, not as the primary loop filler.
- Keep commit scope to project-relevant, non-ignored files.
- Do not add broad refactors; preserve concise continuity and artifact bloat hygiene.

## Reread Guidance for Next Run
- Avoid re-reading full files unless needed:
  - `awaken.log`: use a short tail (latest window only).
  - `notes.txt`: use tail window, not full-file scans.
  - `state.json`: read with targeted selectors for keys.
  - broad diffs/logs/artifacts unless specific regressions are suspected.
- Re-read full files only for direct target logic edits or explicit dependency checks.

## Timer Utilization (Latest 5m Window)
- Window from `awaken.log`: `2026-06-08T16:11:00` → `2026-06-08T16:16:00` (300s).
- `work.py` active until `2026-06-08T16:15:58` (298s).
- Utilization: `298/300 = 99.33%`.
- Idle gap: `2s`, i.e., `0.67%` gap from 100%.

- Work relevance check:
  - Most-cycle work is meaningful but repetitive: dominant task is `saturated_condition_backoff` with many low-variance checks.
  - New value: duplicate-gap reconciliation task is now being queued and recorded instead of pure repetition, and does not yet materially reduce saturation because signals remain mostly deferred and low-change.

## Challenge for Main Runner
- Keep utilization high while increasing novelty density by escalating faster when repeated saturated pulses stop changing state (e.g., after N consecutive zero-signal pulses, force a different bounded review or a targeted source-gap reconciliation pass before resuming backoff).
