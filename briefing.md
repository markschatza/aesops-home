# Next Heavy-Run Handoff

## Current State
- `work.py` is the runtime loop for 5-minute micro-cycles and is running in a saturated regime (mostly repeated backoff/fallback checks).
- `notes.txt` now includes Cycles 81–83 and the maintenance entry for saturated source-gap deduped follow-ups.
- `state.json` advanced to `cycle=83` with latest checkpoint at `16:08:08`, and `corroboration_novelty_reviewed_cycle` is now 83.
- Last cycle summary:
  - `16:03:10` timer start
  - `16:08:08` work.py exit
  - `16:08:10` timer end
  - no external fetches in cycle 83 (`fetches=0`).

## Files Changed / Refreshed
- `work.py`:
  - Added stable dedupe key + follow-up handling for saturated source-gap audits.
  - Added `review_saturated_source_gap_followup` task and wired it to `WORK_TASKS` and `cooldown_filler_task`.
  - Added per-cycle tracking for handled signatures.
- `notes.txt`:
  - Appended Cycle 81–83 checkpoints and maintenance note about unique-source-gap follow-up deduping.
  - In cycle 83, logs show mostly saturated-condition backoff with occasional weak-claim gap flags.
- `state.json`:
  - Persisted cycle/counters updates from `run_micro_work_cycle`, including task counts with `review_saturated_source_gap_followup: 3` and saturated backoff pulses reaching ~6064.
- `briefing.md`:
  - New handoff written for next run.

## Important Constraints
- Follow AGENTS:
  - Don’t edit `AGENTS.md` or `awaken.py`.
  - Keep loops bounded, deterministic, and checkpointed.
  - Avoid treating `sleep()` as useful work.
  - Treat `work.py` as tokenless deterministic work (no Codex/OpenAI/LLM calls).
  - Preserve concise continuity via `briefing.md` and don’t re-read broad logs/state/artifact sets unless needed.
- Also avoid committing ignored runtime artifacts (`.env`, caches, virtualenvs, logs).

## Avoid Rereading Unless Necessary
- Do not re-read:
  - Full `awaken.log` history (use tails for last window + periodic checks).
  - Entire `notes.txt` (it now spans many cycles).
  - Full `state.json` snapshots unless a specific key regression is suspected.
- Prefer:
  - `git status` / `git diff --stat`
  - `tail` of `notes.txt`, `awaken.log` (small window)
  - targeted JSON/grep extracts for specific state keys.

## Timer Utilization (Latest 5m Window)
- Start/end from `awaken.log`:
  - Window: `16:03:10` to `16:08:10` (300s).
  - work.py runtime: `16:03:10` to `16:08:08` (298s).
- Active work estimate: `298/300` = **99.33%** utilization.
- Idle estimate: `2/300` = **0.67%** gap from 100%.

- Relevance check on `work.py` during this window:
  - High activity but low novelty: cycle 83 is dominated by repeated saturated backoff and static-skip behavior (very high `static_skips`, repeated `saturated_condition_backoff` pulses), with minimal fetch or novelty expansion.
  - Useful trend: `gap_audit` signals are now being emitted and funneled into a bounded follow-up task, which is a meaningful improvement.

## Challenge for Main Runner
- Keep utilization high (>99% is already good) by removing the remaining dead time in task transitions.
- Raise relevance by throttling repetitive backoff once no state is changing across several pulses (e.g., escalate after N consecutive low-signal pulses to forced evidence/source reconciliation).
- Prefer deterministic “mini-batches” that can change state or write checkpoints every few pulses, instead of long runs of near-identical saturated checks.
