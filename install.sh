#!/data/data/com.termux/files/usr/bin/env bash
# Aren AI Agent installer — Ubuntu / Debian / Termux / Oracle free tier
# Free forever: only free/local components are used.
set -e

echo "[aren] installing for: ${PREFIX:-/} ($(uname -o 2>/dev/null || uname -s))"

# 1) python3 (Termux/Ubuntu/Debian)
if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y && apt-get install -y python3
  elif command -v pkg >/dev/null 2>&1; then
    pkg install -y python
  else
    echo "[aren] ERROR: please install python3 manually" >&2
    exit 1
  fi
fi

# 2) optional but recommended extras (never fatal if they fail)
PKG_MGR=""
if command -v pkg >/dev/null 2>&1; then PKG_MGR=pkg; fi
if command -v apt-get >/dev/null 2>&1; then PKG_MGR=apt; fi

if [ -n "$PKG_MGR" ]; then
  echo "[aren] installing optional extras (notifications, voice, curl)..."
  if [ "$PKG_MGR" = pkg ]; then
    pkg install -y termux-api espeak curl >/dev/null 2>&1 || true
  else
    apt-get install -y notify-send espeak curl >/dev/null 2>&1 || true
  fi
fi

# 3) ollama (local, free brain) — skip on Termux (no official build) unless present
if command -v ollama >/dev/null 2>&1; then
  echo "[aren] ollama already installed"
elif command -v curl >/dev/null 2>&1 && [ "$(uname -o 2>/dev/null)" != "Android" ]; then
  echo "[aren] installing ollama (free local LLM runtime)..."
  curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1 || \
    echo "[aren] WARN: ollama install failed — install later from https://ollama.com"
else
  echo "[aren] NOTE: ollama not available here; use any free OpenAI-compatible API in aren.config.json"
fi

# 4) default model (skip on very small devices)
if command -v ollama >/dev/null 2>&1 && ! ollama list 2>/dev/null | grep -q qwen; then
  echo "[aren] pulling default model qwen2.5:3b (small, fast)..."
  ollama pull qwen2.5:3b >/dev/null 2>&1 || \
    echo "[aren] WARN: model pull failed — run 'ollama pull qwen2.5:3b' later"
fi

# 5) finish
cat <<'EOF'

  Aren installed.

  Start it:
      aren            (interactive chat)
      aren daemon     (always-on background agent)

  First command to try:
      aren research "best free vps 2026"
      aren run "uname -a"
      aren remind "drink water" in 20 min

EOF
echo "[aren] done. free forever. no credits. no expiry."
