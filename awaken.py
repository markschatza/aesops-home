#!/usr/bin/env python3
# Aesop's Heartbeat Begins

from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import time

WORK_SCRIPT = Path(__file__).with_name("work.py")
BRIEFING = Path(__file__).with_name("briefing.md")
AWAKEN_LOG = Path(__file__).with_name("awaken.log")
CODEX_LOG = Path(__file__).with_name("codex.log")
CODEX_LAST_MESSAGE = Path(__file__).with_name("codex-last-message.txt")
WORK_INTERVAL_SECONDS = 5 * 60
SPARK_MODEL = os.environ.get("CODEX_SPARK_MODEL", "gpt-5.3-codex-spark")
MAIN_MODEL = os.environ.get("CODEX_MAIN_MODEL", "gpt-5.5")


def timestamp():
    return datetime.now().isoformat(timespec="seconds")


def interval_label():
    minutes, seconds = divmod(WORK_INTERVAL_SECONDS, 60)
    if seconds:
        return f"{minutes}m {seconds}s"
    return f"{minutes}m"


def log_event(message):
    line = f"[{timestamp()}] {message}"
    print(line, flush=True)
    with AWAKEN_LOG.open("a", encoding="utf-8") as log:
        log.write(line + "\n")


def run_codex(prompt, *, model=None, label="codex"):
    model_note = f" with {model}" if model else ""
    print(f"starting {label} exec{model_note}", flush=True)
    CODEX_LAST_MESSAGE.unlink(missing_ok=True)
    command = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "--output-last-message",
        str(CODEX_LAST_MESSAGE),
    ]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    with CODEX_LOG.open("a") as log:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode != 0:
        print(f"{label} exec exited with code {result.returncode}", flush=True)
    else:
        print(f"{label} exec finished", flush=True)
    if CODEX_LAST_MESSAGE.exists():
        final_message = CODEX_LAST_MESSAGE.read_text().strip()
        if final_message:
            print(f"\n--- {label} final response ---", flush=True)
            print(final_message, flush=True)
            print(f"--- end {label} final response ---\n", flush=True)
    return result.returncode == 0


def prepare_briefing():
    ok = run_codex(
        (
            "Prepare the next heavy-run handoff without overflowing context. Read AGENTS.md fully. "
            "Preserve context by avoiding full reads of large logs, state files, caches, generated artifacts, "
            "or broad artifact sets. Prefer recent tails, git diff/status, metadata, and compact Python summaries. "
            "Read full files only when they are the direct target of the handoff or needed to verify a specific logic dependency. "
            f"Write a concise {BRIEFING.name} for the next heavier Codex run. Include: "
            "current state, files changed or refreshed, important constraints, "
            "and anything the heavier model should avoid rereading unless necessary. "
            "Always include a 'Timer Utilization' section. Use awaken.log timestamps to estimate "
            f"how much of the latest {interval_label()} work.py window was active work versus idle waiting, "
            "and state the gap from 100% utilization. Review work.py itself to judge whether the active "
            "time is relevant and interesting work. Using sleep() to wait between tasks is not a real use of time. It is simply filling dead space. The timer window should be spent on bounded useful work: interesting code, deterministic analysis, local computation, careful artifact review, or targeted research when it is genuinely needed. Challenge the main runner to improve both utilization percent and the relevance of the work done during that time. "
            "Keep it under 800 words. After writing briefing.md, commit the latest non-ignored project changes, including notes.txt and briefing.md, with a concise commit message. Do not commit ignored runtime logs, virtualenvs, caches, or .env files. Push the commit if a git remote is configured; if no remote is configured, say that clearly in the final response."
        ),
        model=SPARK_MODEL,
        label="spark briefing",
    )
    if not ok:
        print(f"spark briefing failed; keeping existing {BRIEFING.name}", flush=True)


def run_main_continuation(prompt):
    run_codex(
        (
            f"{prompt}\n\n"
            "Start by reading briefing.md for latest changes and then decide next step towards your larger goal. "
            "Preserve context by avoiding full reads of large logs, state files, caches, generated artifacts, "
            "or broad artifact sets. Prefer recent tails, git diff/status, metadata, and compact Python summaries. "
            "Read only the target files needed for the next edit. "
            f"Treat full use of the {interval_label()} work.py timer as a standing objective: each turn should "
            "look for one small way to make work.py spend more of its window on useful bounded work, checkpoint "
            "progress frequently, and avoid exiting early into idle sleep. "
            "For broad scanning, summarization, or code writing that should use cheaper Spark quota, "
            "use the spark-subprocess-subagent skill instead of native subagents."
        ),
        model=MAIN_MODEL,
        label="main codex",
    )


prepare_briefing()
run_main_continuation("Read AGENTS.md and start your journey!")

while True:
    started_at = time.monotonic()
    timer_started = datetime.now()
    timer_ends = timer_started + timedelta(seconds=WORK_INTERVAL_SECONDS)
    log_event(f"{interval_label()} timer started; ends at {timer_ends.isoformat(timespec='seconds')}")
    worker = subprocess.Popen([sys.executable, str(WORK_SCRIPT)])
    try:
        exit_code = worker.wait(timeout=WORK_INTERVAL_SECONDS)
        log_event(
            f"work.py exited with code {exit_code}; waiting until {timer_ends.isoformat(timespec='seconds')}"
        )
    except subprocess.TimeoutExpired:
        log_event(f"{interval_label()} timer ended; killing work.py")
        worker.kill()
        worker.wait()
    remaining = WORK_INTERVAL_SECONDS - (time.monotonic() - started_at)
    if remaining > 0:
        time.sleep(remaining)
    log_event(f"{interval_label()} timer ended; preparing briefing")
    prepare_briefing()
    log_event("briefing ready; running codex continuation")
    run_main_continuation("Continue from the last run.")
