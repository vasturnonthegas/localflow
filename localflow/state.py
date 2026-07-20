"""Shared dictation state on disk, so the menu bar (a separate process) can
reflect what the dictation app is doing and re-copy recent transcripts.

The dictation app (`localflow.app`) is the only writer; the menu bar only
reads. Writes are atomic (temp file + os.replace) so a concurrent reader
never sees a half-written file, and every call swallows its own errors —
state reporting must never break dictation itself.
"""

import json
import os
import time
from pathlib import Path

STATE_DIR = Path.home() / ".localflow"
STATUS_PATH = STATE_DIR / "dictation.json"
HISTORY_PATH = STATE_DIR / "history.jsonl"

HISTORY_LIMIT = 20
# A non-idle status this old is treated as stale — the app crashed mid-clip,
# so we don't leave a stuck "recording" indicator in the menu bar forever.
STALE_SECONDS = 120


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def set_status(status: str) -> None:
    """Record current dictation status: 'idle' | 'recording' | 'transcribing'."""
    try:
        _atomic_write(
            STATUS_PATH,
            json.dumps(
                {"status": status, "pid": os.getpid(), "updated": time.time()}
            ),
        )
    except Exception:
        pass


def read_status() -> dict:
    """Return {'status', 'pid', 'updated', 'running'}.

    'running' is a live pid probe of the writing process, so the menu bar can
    tell a running dictation app from a stale file left behind by a crash or a
    previous run. A non-idle status is downgraded to 'idle' if the writer is
    gone or the entry is stale.
    """
    default = {"status": "idle", "pid": None, "updated": 0.0, "running": False}
    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default
    running = _pid_alive(data.get("pid"))
    status = data.get("status", "idle")
    if not running:
        status = "idle"
    elif status != "idle" and time.time() - data.get("updated", 0) > STALE_SECONDS:
        status = "idle"
    data["status"] = status
    data["running"] = running
    return data


def add_transcript(text: str, ms: int) -> None:
    """Append a transcript to history, keeping only the most recent entries."""
    text = (text or "").strip()
    if not text:
        return
    try:
        entry = json.dumps({"text": text, "ms": int(ms), "ts": time.time()})
        lines = []
        if HISTORY_PATH.exists():
            lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        lines.append(entry)
        lines = lines[-HISTORY_LIMIT:]
        _atomic_write(HISTORY_PATH, "\n".join(lines) + "\n")
    except Exception:
        pass


def read_history(limit: int = HISTORY_LIMIT) -> list[dict]:
    """Most-recent-first list of {'text', 'ms', 'ts'} transcript entries."""
    try:
        lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    out.reverse()
    return out
