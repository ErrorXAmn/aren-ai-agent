#!/usr/bin/env python3
"""
Aren AI Agent - always-on daemon
================================
Keeps Aren alive in the background so scheduled jobs and reminders keep
working even when the chat loop is closed. Runs fine under:

  * nohup / systemd / cron            (Ubuntu, Oracle free tier VPS)
  * termux-services (sv-enable)       (Termux on Android)

What it does:
  * fires due reminders as notifications
  * runs jobs from ~/aren_data/jobs.json  (see README for format)
"""

import json
import os
import time

from .tools import _data_dir, _read_json, _write_json, run_tool


def load_jobs() -> list:
    return _read_json(os.path.join(_data_dir(), "jobs.json"), [])


def save_jobs(jobs: list) -> None:
    _write_json(os.path.join(_data_dir(), "jobs.json"), jobs)


def fire_due_reminders() -> None:
    path = os.path.join(_data_dir(), "reminders.json")
    data = _read_json(path, [])
    now = time.time()
    due = [r for r in data if float(r.get("at", 0)) <= now]
    if not due:
        return
    _write_json(path, [r for r in data if float(r.get("at", 0)) > now])
    for r in due:
        run_tool("notify", {"title": "Aren reminder", "message": str(r.get("text", ""))})


def run_due_jobs(brain) -> None:  # noqa: ANN001 - avoids an import cycle
    jobs = load_jobs()
    now = time.time()
    changed = False
    for job in jobs:
        if float(job.get("next_run", 0)) > now:
            continue
        task = str(job.get("task", "")).strip()
        if task:
            try:
                out = brain.run(task)
            except Exception as exc:  # noqa: BLE001
                out = f"error: {exc}"
            run_tool("notify", {"title": f"Aren job: {task[:40]}", "message": out[:300]})
        interval = int(job.get("interval_minutes", 60))
        job["next_run"] = now + interval * 60
        changed = True
    if changed:
        save_jobs(jobs)


def main() -> int:
    from .brain import Brain  # local import keeps daemon startup light

    brain = Brain()
    print(f"[aren-daemon] backend={brain.backend} model={brain.model or '(offline)'}")
    print(f"[aren-daemon] watching {_data_dir()} for reminders and jobs.json")
    while True:
        try:
            fire_due_reminders()
            run_due_jobs(brain)
        except KeyboardInterrupt:
            print("\n[aren-daemon] stopped.")
            return 0
        except Exception as exc:  # noqa: BLE001 - a daemon must never die
            print(f"[aren-daemon] recoverable error: {exc}")
        time.sleep(20)


if __name__ == "__main__":
    import sys

    sys.exit(main())
