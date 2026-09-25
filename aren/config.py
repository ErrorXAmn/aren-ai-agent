#!/usr/bin/env python3
"""Aren AI Agent - configuration loader. Free forever, no accounts."""

import json
import os
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    # "auto" tries: Ollama (local, free) -> any OpenAI-compatible endpoint
    #               (free tiers / self-hosted) -> OPENAI_API_KEY if present.
    # With no backend found, Aren still works using the offline planner.
    "backend": "auto",
    "model": "",  # empty = auto-pick (qwen2.5:7b on Ollama, else first available)
    "base_url": "",  # for OpenAI-compatible endpoints, e.g. a free-tier router
    "api_key": "",  # only needed for OpenAI-compatible endpoints
    "max_steps": 12,  # per task; keeps runaway loops finite
    "deep_think": True,  # high-brain mode: extra reasoning pass each step
    "allow_dangerous": False,  # rm -rf etc. Stay off unless you know why.
    "shell_timeout": 20,
    "research_max_results": 8,
    "persona": (
        "You are Aren, a decisive terminal AI agent running on the user's own "
        "machine or phone (Ubuntu, Debian, Termux, Oracle free tier). You do "
        "the whole task with real tool calls, never invent tool output, and "
        "you finish with a crisp result."
    ),
}


def config_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "aren.config.json",
    )


def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except (json.JSONDecodeError, OSError):
            pass  # broken file -> fall back to defaults, never crash
    # Environment always wins so secrets never live in files.
    for env_key, cfg_key in (
        ("AREN_MODEL", "model"),
        ("AREN_BACKEND", "backend"),
        ("AREN_BASE_URL", "base_url"),
        ("OPENAI_API_KEY", "api_key"),
        ("AREN_API_KEY", "api_key"),
    ):
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val
    return cfg


def save_config(updates: Dict[str, Any]) -> None:
    cfg = load_config()
    cfg.update(updates)
    with open(config_path(), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
