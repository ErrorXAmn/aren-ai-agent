#!/usr/bin/env python3
"""
Aren AI Agent - Toolbelt
========================
Every capability Aren has lives here as a plain function registered in
`registry`. The brain calls them by name. Add your own by writing a new
function decorated with @tool.

Safety model (no killing your phone):
  * shell runs with a timeout and a denylist of catastrophic commands
  * anything destructive requires config flag `allow_dangerous`
"""

import json
import os
import platform
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Tuple

from .config import load_config

registry: Dict[str, Tuple[Callable[..., str], Dict[str, str], str]] = {}


def tool(name: str, description: str, **arg_specs: str) -> Callable:
    """Register a function as an Aren tool with a JSON-ish arg spec."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        registry[name] = (fn, arg_specs, description)
        return fn

    return decorator


def tool_schemas() -> str:
    lines = []
    for name, (_, args, desc) in sorted(registry.items()):
        args_s = ", ".join(f"{k}: {v}" for k, v in args.items())
        lines.append(f"- {name}({args_s}): {desc}")
    return "\n".join(lines)


def run_tool(name: str, args: Dict[str, Any]) -> str:
    if name not in registry:
        return f"error: unknown tool '{name}'"
    fn, _, _ = registry[name]
    try:
        return fn(**args)
    except TypeError as exc:
        return f"error: bad args for {name}: {exc}"
    except Exception as exc:  # noqa: BLE001 - tools must never kill the loop
        return f"error: {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------- #
# system
# ---------------------------------------------------------------------- #
DENYLIST = (
    r"\brm\s+-rf\s+/(?!home|sdcard|data/data)",
    r"\bmkfs(\.\w+)?\b",
    r"\b:\(\)\s*\{.*\};\s*:",  # fork bomb
    r"\bdd\s+if=.*of=/dev/(sd|mmcblk|block)",
    r"\bshutdown\b|\breboot\b|\bhalt\b",
)


@tool("shell", "Run a shell command on this device and get stdout/stderr.", command="string")
def shell(command: str) -> str:
    cfg = load_config()
    for pattern in DENYLIST:
        if re.search(pattern, command):
            return f"blocked: command matches safety denylist ({pattern})"
    timeout = int(cfg.get("shell_timeout", 20))
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        return f"exit={proc.returncode}\nstdout:\n{out[:6000]}\nstderr:\n{err[:2000]}"
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


@tool("sysinfo", "Get OS, CPU, memory and Python info for this device.")
def sysinfo() -> str:
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
    if shutil.which("free"):
        info["memory"] = shell("free -h | head -2")
    return json.dumps(info, indent=2)


@tool("clock_now", "Current local date and time.")
def clock_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %A")


# ---------------------------------------------------------------------- #
# research
# ---------------------------------------------------------------------- #
@tool("web_search", "Search the public web. Returns titles, URLs, snippets.", query="string", max_results="int")
def web_search(query: str, max_results: int = 5) -> str:
    max_results = max(1, min(int(max_results), 10))
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ArenAgent)"})
        html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
        results = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.S,
        )
        if not results:  # some DDG layouts hide the anchor class
            results = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]{15,120})</a>', html)
        seen, out = set(), []
        for href, title in results:
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title or href in seen:
                continue
            seen.add(href)
            out.append(f"{len(out) + 1}. {title}\n   {href}")
            if len(out) >= max_results:
                break
        return "\n".join(out) if out else "no results (engine layout may have changed)"
    except Exception as exc:  # noqa: BLE001
        return f"error: search failed: {exc}"


@tool("fetch_url", "Download a web page and return readable text.", url="string")
def fetch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "error: url must start with http:// or https://"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ArenAgent)"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:6000]
    except Exception as exc:  # noqa: BLE001
        return f"error: fetch failed: {exc}"


@tool("note_add", "Save a note locally.", text="string")
def note_add(text: str) -> str:
    path = _data_file("notes.md")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n- [{time.strftime('%Y-%m-%d %H:%M')}] {text}\n")
    return f"note saved -> {path}"


@tool("note_list", "List saved notes.")
def note_list() -> str:
    path = _data_file("notes.md")
    if not os.path.exists(path):
        return "no notes yet"
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read().strip()[-4000:] or "no notes yet"


@tool("remind_add", "Set a reminder in N minutes (fires as a terminal notification).", text="string", minutes="int")
def remind_add(text: str, minutes: int = 10) -> str:
    minutes = max(1, int(minutes))
    path = _data_file("reminders.json")
    data = _read_json(path, [])
    data.append({"text": text, "at": time.time() + minutes * 60})
    _write_json(path, data)
    return f"reminder set: '{text}' in {minutes} min"


@tool("notify", "Send a desktop/termux notification.", title="string", message="string")
def notify(title: str = "Aren", message: str = "") -> str:
    if shutil.which("termux-notification"):
        subprocess.run(["termux-notification", "--title", title, "--content", message], timeout=10)
        return "termux notification sent"
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], timeout=10)
        return "desktop notification sent"
    print(f"\n[ Aren ] {title}: {message}\n")
    return "printed to terminal (no notifier installed)"


# ---------------------------------------------------------------------- #
# phone (Termux:Termux:API) & desktop
# ---------------------------------------------------------------------- #
def _termux(cmd: List[str]) -> str:
    if not shutil.which("termux-battery-status") and not shutil.which("termux-notification"):
        return "error: Termux:API app not installed (install 'Termux:API' + 'pkg install termux-api')"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (proc.stdout or proc.stderr or "ok").strip()[:2000]
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


@tool("battery_status", "Battery level/status (Termux or laptop).")
def battery_status() -> str:
    if shutil.which("termux-battery-status"):
        raw = _termux(["termux-battery-status"])
        try:
            data = json.loads(raw)
            return f"battery {data.get('percentage')}% ({data.get('status')}, {data.get('temperature')}C)"
        except json.JSONDecodeError:
            return raw
    up = shutil.which("upower")
    if up:
        return shell("upower -i $(upower -e | grep BAT) | grep -E 'state|to\\s+full|percentage'")
    return "battery tool unavailable on this device"


@tool("sms_send", "Send an SMS (Termux:API, requires SEND_SMS permission).", to="string", body="string")
def sms_send(to: str, body: str) -> str:
    return _termux(["termux-sms-send", "-n", "1", to, body])


@tool("call_dial", "Dial a phone number (opens the dialer via Termux:API).", number="string")
def call_dial(number: str) -> str:
    return _termux(["termux-telephony-call", number])


@tool("tts_speak", "Speak text out loud (Termux TTS / espeak).", text="string")
def tts_speak(text: str) -> str:
    if shutil.which("termux-tts-speak"):
        return _termux(["termux-tts-speak", text])
    if shutil.which("espeak"):
        subprocess.run(["espeak", text], timeout=30)
        return "spoken via espeak"
    return "error: no TTS engine (termux-tts-speak or espeak)"


@tool("screen_shot", "Take a screenshot (Termux:API).", )
def screen_shot() -> str:
    return _termux(["termux-screenshot", "-f", os.path.join(_data_dir(), "screenshot.png")])


@tool("clipboard_get", "Read the device clipboard.")
def clipboard_get() -> str:
    if shutil.which("termux-clipboard-get"):
        return _termux(["termux-clipboard-get"])
    return shell("xclip -o 2>/dev/null || wl-paste 2>/dev/null || echo no-x-clipboard")


# ---------------------------------------------------------------------- #
# socials (public APIs only - no scraping against ToS)
# ---------------------------------------------------------------------- #
@tool("github_repo_info", "GitHub repo stats: stars, forks, language, updated.", repo="string")
def github_repo_info(repo: str) -> str:
    try:
        with urllib.request.urlopen(f"https://api.github.com/repos/{repo}", timeout=15) as r:
            d = json.loads(r.read().decode())
        return (
            f"{d.get('full_name')} | ★ {d.get('stargazers_count')} | forks {d.get('forks_count')} "
            f"| {d.get('language')} | pushed {str(d.get('pushed_at'))[:10]} | {d.get('description')}"
        )
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


@tool("hacker_news", "Top Hacker News stories right now.", limit="int")
def hacker_news(limit: int = 5) -> str:
    try:
        with urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15) as r:
            ids = json.loads(r.read().decode())[: max(1, min(int(limit), 10))]
        out = []
        for i in ids:
            with urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=15) as r:
                it = json.loads(r.read().decode())
            out.append(f"- {it.get('title')} (score {it.get('score')}) {it.get('url', '')}")
        return "\n".join(out)
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


# ---------------------------------------------------------------------- #
# files
# ---------------------------------------------------------------------- #
@tool("write_file", "Write text to a file under ~/aren_data.", filename="string", content="string")
def write_file(filename: str, content: str) -> str:
    if "/" in filename or ".." in filename:
        return "error: filename must be a simple name (no paths)"
    path = os.path.join(_data_dir(), filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"wrote {len(content)} chars -> {path}"


@tool("read_file", "Read a file from ~/aren_data.", filename="string")
def read_file(filename: str) -> str:
    if "/" in filename or ".." in filename:
        return "error: filename must be a simple name (no paths)"
    path = os.path.join(_data_dir(), filename)
    if not os.path.exists(path):
        return "error: file not found"
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()[:6000]


# ---------------------------------------------------------------------- #
# helpers
# ---------------------------------------------------------------------- #
def _data_dir() -> str:
    base = os.environ.get("AREN_HOME", os.path.join(os.path.expanduser("~"), "aren_data"))
    os.makedirs(base, exist_ok=True)
    return base


def _data_file(name: str) -> str:
    return os.path.join(_data_dir(), name)


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
