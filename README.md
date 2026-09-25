# Aren AI Agent

<p align="center">
  <b>Terminal-based AI agent for Ubuntu, Debian, Termux & Oracle free tier.</b><br/>
  Research anything · control your phone · automate everything · free forever · no credits · no expiry
</p>

---

## Why Aren

| | Aren | Typical cloud agent |
|---|---|---|
| Price | **₹0 forever** (local models, free APIs) | monthly credits |
| Runs on | your phone/PC/VPS — **your hardware** | someone else's cloud |
| Privacy | 100% local when using Ollama | your data on their servers |
| Works on | Termux (Android), Ubuntu, Debian, Oracle ARM free tier | mostly laptops |
| Always-on | daemon + cron + systemd + Oracle | only while you pay |

## Features

- 🧠 **High-reasoning brain** — agentic loop `THINK → PLAN → ACT → OBSERVE` with a deep-think pass before every action.
- 🔎 **Research anything** — web search + page fetch + summarization, unlimited, no API key needed.
- 📱 **Phone control** (Termux:API) — SMS, calls, TTS, clipboard, battery, screenshots.
- 💻 **PC in your phone** — full shell access on any device; run it on an Oracle free-tier VPS and reach your "PC" from anywhere via SSH.
- 🗣️ **Socials & accounts** — GitHub/HN stats now, pluggable X/Telegram/WhatsApp via API bridges.
- ⏰ **Always-on daemon** — reminders + scheduled jobs (`jobs.json`) keep running after you close the terminal.
- 🧩 **Unlimited tools** — add your own with one `@tool` decorator; Aren discovers them automatically.
- 🔒 **Safe by default** — shell denylist, timeouts, destructive-command guard.
- 🆓 **No credit expire** — pure stdlib Python; bring your own free model (Ollama local or any free OpenAI-compatible endpoint).

## Quick start

```bash
git clone https://github.com/ErrorXAmn/aren-ai-agent.git
cd aren-ai-agent
bash install.sh
aren
```

Full manual (Termux):

```bash
pkg update && pkg install python git -y
git clone https://github.com/ErrorXAmn/aren-ai-agent.git
cd aren-ai-agent
python -m aren
```

Ubuntu / Oracle VPS:

```bash
sudo apt update && sudo apt install -y python3 git curl
git clone https://github.com/ErrorXAmn/aren-ai-agent.git
cd aren-ai-agent
bash install.sh
```

## Giving Aren a brain (all free)

**Option A — local, offline, private (recommended):**

```bash
ollama pull qwen2.5:3b     # or 7b if you have 8GB+ RAM
```

**Option B — any free OpenAI-compatible API:** create `aren.config.json`:

```json
{
  "backend": "openai",
  "base_url": "https://YOUR-FREE-PROVIDER/v1",
  "api_key": "free-key-here",
  "model": "model-name"
}
```

No backend at all? Aren still works in **offline planner mode** for search, shell, notes, reminders.

## Always-on (Oracle free tier)

1. Create an **Oracle Cloud Always Free ARM** instance (4 OCPU / 24GB — genuinely free, no expiry).
2. `bash install.sh` on it, then:

```bash
# keep Aren alive forever
sudo tee /etc/systemd/system/aren.service <<'EOF'
[Unit]
Description=Aren AI Agent daemon
After=network.target

[Service]
ExecStart=/usr/bin/env python3 -m aren.daemon
Restart=always
User=ubuntu
WorkingDirectory=/home/ubuntu/aren-ai-agent

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now aren
```

3. SSH in from Termux anytime: your PC-in-phone is live. `pc-in-phone` helper:

```bash
ssh ubuntu@YOUR_ORACLE_IP "cd aren-ai-agent && python3 -m aren 'research sunrise time delhi'"
```

## Scheduled jobs

`~/aren_data/jobs.json`:

```json
[
  { "task": "research bitcoin price", "interval_minutes": 60, "next_run": 0 }
]
```

The daemon picks it up automatically and notifies you with results.

## Adding your own tools (unlimited features)

```python
# aren/tools.py — add anywhere:
@tool("insta_followers", "Public follower count for an Instagram account.", user="string")
def insta_followers(user: str) -> str:
    ...your code...
```

Aren discovers new tools automatically — no registration anywhere else.

## Safety

- Shell commands pass a denylist (`rm -rf /`, fork bombs, disk wipes, shutdown).
- Commands run with timeouts; nothing hangs your phone.
- Destructive actions need `allow_dangerous: true` in `aren.config.json`.
- Phone tools need explicit Termux:API permissions, granted by you.

## Disclaimer

Phone/social automation is powerful — use it on your own accounts and devices, and respect the terms of service of every platform you connect. The authors are not responsible for misuse.

## License

MIT — free forever.
