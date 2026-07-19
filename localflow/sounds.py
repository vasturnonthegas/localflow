"""Short audio cues via macOS system sounds (afplay, non-blocking)."""

import subprocess

_SOUNDS = {
    "start": "/System/Library/Sounds/Pop.aiff",
    "stop": "/System/Library/Sounds/Bottle.aiff",
}


def play(cue: str) -> None:
    path = _SOUNDS.get(cue)
    if not path:
        return
    try:
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # a missing sound must never break recording
