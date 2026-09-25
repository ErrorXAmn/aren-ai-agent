#!/usr/bin/env python3
"""
Aren AI Agent - Core Engine ("The Brain")
=========================================
The heart of Aren. Runs an agentic loop:

    THINK -> PLAN -> ACT (run tools) -> OBSERVE -> REPEAT
    until the task is done. Then respond.

Design goals:
  * Zero paid API dependency. Works with Ollama (local, free) or any
    OpenAI-compatible endpoint (free tiers, self-hosted vLLM, etc).
  * High-reasoning mode: a hidden "think" pass before every action so
    even small models behave like a careful agent.
  * If no model backend is reachable, a deterministic offline planner
    still gets real work done (search, shell, notes, reminders).
"""

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .config import load_config
from .tools import registry, run_tool, tool_schemas

SYSTEM_PROMPT = """You are Aren, an autonomous terminal AI agent.
You solve the user's task by calling tools, one JSON action at a time.

Respond with ONLY a JSON object on every turn:
  {"think": "<brief private reasoning>", "action": {"tool": "<name>", "args": {...}}}
or, when the task is complete:
  {"think": "<brief reasoning>", "final": "<answer for the user>"}

Rules:
- Never invent tool output. Observe, then decide.
- Prefer the fewest steps that fully finish the task.
- If something is impossible with available tools, say so in "final".
"""

OFFLINE_VERBS = {
    "search": "web_search",
    "find": "web_search",
    "research": "web_search",
    "news": "web_search",
    "run": "shell",
    "exec": "shell",
    "install": "shell",
    "note": "note_add",
    "remember": "note_add",
    "remind": "remind_add",
    "notify": "notify",
    "sms": "sms_send",
    "call": "call_dial",
    "battery": "battery_status",
    "tts": "tts_speak",
    "screenshot": "screen_shot",
    "time": "clock_now",
}


class Brain:
    """Wires a model backend (or the offline planner) to the toolbelt."""

    def __init__(self) -> None:
        self.cfg = load_config()
        self.backend, self.model, self.base_url, self.api_key = self._resolve_backend()

    # ------------------------------------------------------------------ #
    # Backend resolution: free-first, zero-config-first.
    # ------------------------------------------------------------------ #
    def _resolve_backend(self) -> Tuple[str, str, str, str]:
        cfg = self.cfg
        backend = cfg.get("backend", "auto")
        if backend in ("ollama", "openai", "offline"):
            return backend, cfg.get("model", ""), cfg.get("base_url", ""), cfg.get("api_key", "")

        # auto: Ollama -> OpenAI-compatible -> offline
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            models = [m.get("name", "") for m in data.get("models", [])]
            model = cfg.get("model") or next((m for m in models if "qwen" in m), models[0] if models else "")
            return "ollama", model, "http://127.0.0.1:11434", ""
        except Exception:
            pass
        if cfg.get("base_url") or cfg.get("api_key"):
            return "openai", cfg.get("model", ""), cfg.get("base_url", "https://api.openai.com/v1"), cfg.get("api_key", "")
        return "offline", "", "", ""

    # ------------------------------------------------------------------ #
    # Public entry: run one user task to completion.
    # ------------------------------------------------------------------ #
    def run(self, task: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        if self.backend == "offline":
            return self._offline_plan(task)
        messages: List[Dict[str, str]] = [{"role": "system", "content": self._system()}]
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": task})

        for _ in range(int(self.cfg.get("max_steps", 12))):
            raw = self._chat(messages)
            think, action, final = self._parse(raw)
            if final is not None:
                return final
            if not action:
                return think or "I could not decide on a next action."
            tool, args = action
            if tool == "task_done":
                return str(args.get("summary", "Done."))
            observation = run_tool(tool, args)
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{observation}\n\nNext JSON action:"})
        return "Stopped: step limit reached. Partial progress is in the transcript."

    # ------------------------------------------------------------------ #
    # Model plumbing
    # ------------------------------------------------------------------ #
    def _system(self) -> str:
        persona = self.cfg.get("persona", "")
        return (
            f"{persona}\n\n{SYSTEM_PROMPT}\nAvailable tools:\n{tool_schemas()}"
            + ("\nDeep-think mode: use \"think\" to reason step by step before acting."
               if self.cfg.get("deep_think", True) else "")
        )

    def _chat(self, messages: List[Dict[str, str]]) -> str:
        if self.backend == "ollama":
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.2},
            }
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8", "ignore")).get("message", {}).get("content", "")
        # OpenAI-compatible
        payload = {"model": self.model, "messages": messages, "temperature": 0.2}
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            return json.dumps({"error": f"HTTP {exc.code}: {exc.reason}"})

    @staticmethod
    def _parse(raw: str) -> Tuple[str, Optional[Tuple[str, Dict[str, Any]]], Optional[str]]:
        """Extract think/action/final from a model reply (robust to prose)."""
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return raw.strip(), None, None
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            return raw.strip(), None, None
        think = str(obj.get("think", ""))
        if "final" in obj:
            return think, None, str(obj["final"])
        action = obj.get("action") or {}
        tool = action.get("tool")
        if tool and tool in registry:
            return think, (tool, action.get("args") or {}), None
        return think, None, f"Unknown tool '{tool}'. Available: {', '.join(sorted(registry))}"

    # ------------------------------------------------------------------ #
    # Offline planner: no model needed, still genuinely useful.
    # ------------------------------------------------------------------ #
    def _offline_plan(self, task: str) -> str:
        words = task.lower().split()
        verb = next((OFFLINE_VERBS[w] for w in words if w in OFFLINE_VERBS), None)
        if verb is None:
            return (
                "Offline mode: no model backend found.\n"
                "Install Ollama (free) and pull a model, e.g.:\n"
                "  ollama pull qwen2.5:7b\n"
                "Then rerun. Meanwhile these commands work:\n"
                "  aren run <shell command>\n"
                "  aren research <topic>\n"
                "  aren note <text>\n"
                "  aren remind <text> in <minutes> min\n"
                "  aren tools\n"
            )
        if verb == "web_search":
            query = task
            for stop in ("search", "find", "research", "news", "about", "for"):
                query = re.sub(rf"\b{stop}\b", " ", query, flags=re.I)
            return run_tool("web_search", {"query": query.strip() or task, "max_results": 5})
        if verb == "shell":
            return run_tool("shell", {"command": task.split(" ", 1)[-1]})
        if verb == "note_add":
            return run_tool("note_add", {"text": task})
        if verb == "remind_add":
            minutes = 10
            m = re.search(r"(\d+)\s*(?:min|minute)", task.lower())
            if m:
                minutes = int(m.group(1))
            return run_tool("remind_add", {"text": task, "minutes": minutes})
        return run_tool(verb, {})
