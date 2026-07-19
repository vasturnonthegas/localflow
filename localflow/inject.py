import subprocess
import time

import pyperclip


def paste_text(text: str) -> None:
    old_clipboard = None
    try:
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = None

        pyperclip.copy(text)

        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            check=False,
        )

        time.sleep(0.3)
    except Exception:
        pass
    finally:
        if old_clipboard is not None:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
