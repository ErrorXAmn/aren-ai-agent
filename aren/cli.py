#!/usr/bin/env python3
"""Aren AI Agent - terminal CLI. Type a task in plain language."""

import sys

from .brain import Brain
from .tools import registry, run_tool

BANNER = r"""
    ___
   /   |   ______ ___________
  / /| | / ___// ___/ ___/ _ \
 / ___ |(__  )/ /__(__  )/ __/
/_/  |_/____/ \___/____/ \___/
Aren AI Agent - terminal AI that does the work
"""

HELP = """Commands:
  <any text>            Give Aren a task in plain language
  /tools                List every tool Aren can use
  /run <cmd>            Run a shell command directly (no AI)
  /sysinfo              Device report
  /help                 This help
  /quit | /exit         Leave Aren
"""


def _chat_history() -> list:
    # a light in-memory history; fresh per session is fine for a terminal tool
    return []


def main() -> int:
    print(BANNER)
    brain = Brain()
    if brain.backend == "offline":
        print("[aren] offline planner mode (research, shell, notes, reminders work)")
        print("[aren] full brain ke liye chat me type karo: ollama")
    else:
        print(f"[aren] backend={brain.backend} model={brain.model or '(default)'}")
    print("[aren] type /help for commands. Ctrl-D or /quit to exit.\n")

    history = _chat_history()
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[aren] bye.")
            return 0
        if not line:
            continue
        if line in ("/quit", "/exit", "quit", "exit"):
            print("[aren] bye.")
            return 0
        if line == "/help":
            print(HELP)
            continue
        if line == "/tools":
            for name in sorted(registry):
                _, _, desc = registry[name]
                print(f"  {name:<18} {desc}")
            continue
        if line.startswith("/run "):
            print(run_tool("shell", {"command": line[5:]}))
            continue
        if line == "/sysinfo":
            print(run_tool("sysinfo", {}))
            continue

        try:
            answer = brain.run(line, history=history)
        except Exception as exc:  # noqa: BLE001 - the CLI must survive anything
            answer = f"[aren] internal error: {type(exc).__name__}: {exc}"
        print(f"\naren> {answer}\n")
        history.append({"role": "user", "content": line})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    sys.exit(main())
