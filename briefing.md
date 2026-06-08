# Handoff Briefing (Next Heavy Run)

## Current State
- Cycle is now `33` (`last_run_at: 2026-06-08T12:32:33`).
- Focus remains `sentience welfare radar` and artifact rendering/guardrail checks still run each window.
- `state.json` reflects `next_corroboration_target` set to **Governments and institutions** (`source_quality=preprint`, `source=https://arxiv.org/abs/2603.01508`) and `artifact_snapshot_changed=False`.
- `threshold_sweep_cursor` is `838412500`; min/max sweep scores this window are `0` and `16`.
- `work_queue` now excludes the seeded source fetch at run time and is currently: `audit_artifact_integrity`, `scan_corroboration_markers`, `review_evidence_quality`, `select_corroboration_target`, `audit_guardrails`, `review_uncertainty_coverage`, `refresh_next_queue`.

## Files Changed or Refreshed
- Refreshed in this cycle: `notes.txt`, `state.json`, `work.py`.
- Non-source-cycle artifacts checked but unchanged in snapshot size/hashes: `sentience_welfare_radar.md`, `evidence_notebook.md`, `precaution_checklist.md`, `project_assessments.md`.
- `briefing.md` updated for next handoff.

## Important Constraints
- Do not edit `AGENTS.md` or `awaken.py`.
- Keep `work.py` tokenless and free of LLM/API/subprocess-codex calls.
- Keep web fetches bounded (`MAX_FETCHES_PER_CYCLE` default is 3), short-timeout, and low volume.
- Preserve concise logs; avoid bloating `notes.txt` with non-checkpoint noise.
- Use short, targeted reads (tails/status) for continuity, not full reads of logs/state caches when not needed.

## Things to Avoid Rereading Unless Necessary
- Avoid full `awaken.log` backscroll; use `tail` around the latest window only.
- Avoid complete `source_cache.json` dumps unless cache corruption is suspected.
- Avoid re-reading old `notes.txt` in full; read only recent cycles/checkpoints.
- Reuse the known structure of `work.py` unless changing scheduling/guardrail logic.

## Timer Utilization
- Latest 5m window from `awaken.log`: `2026-06-08T12:32:33` → `2026-06-08T12:37:33`.
- `work.py` exited at `2026-06-08T12:37:27`.
- Estimated active execution: `294s`.
- Estimated idle: `6s` (`300s - 294s`).
- Utilization: `98.0%`; gap to 100%: `2.0%`.
- This is mainly timer tail/handoff spacing, not artificial waiting.

## Relevance Review
- Active work produced meaningful state updates but was dominated by one heavy deterministic task (`run_precaution_threshold_sweep` completed ~70k+ units per subbatch, 70746 total units in `run_precaution_threshold_sweep`).
- Some useful but low-volume tasks still ran: three each of `harvest_source_metadata`, `audit_artifact_integrity`, `scan_corroboration_markers`, `review_evidence_quality`, `select_corroboration_target`, `audit_guardrails`, `review_uncertainty_coverage`, `refresh_next_queue`.
- Relevance risk: long dense runs now show many repetitive scoring batches with little observed state divergence.

## Main Runner Challenge
- Keep utilization near the current `98%`, but improve relevance by reducing repetitive static tasks when artifact snapshots are unchanged.
- Prioritize source-quality actions around unresolved weak claims (`preprint`/`speculative`) before broad deterministic sweeps.
- Add a cheap guard to skip or downsample `run_precaution_threshold_sweep` batches when no input state changed in-cycle.
