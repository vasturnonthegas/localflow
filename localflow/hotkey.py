from collections.abc import Callable

from pynput import keyboard


class HotkeyListener:
    """Toggle mode: a GlobalHotKeys combo like '<cmd>+<shift>+<space>'."""

    def __init__(self, combo: str, on_toggle: Callable[[], None]):
        self.combo = combo
        self.on_toggle = on_toggle

    def run_forever(self) -> None:
        with keyboard.GlobalHotKeys({self.combo: self.on_toggle}) as listener:
            listener.join()


class HoldKeyListener:
    """Push-to-talk mode: hold a single key (e.g. 'alt_l' = left Option).
    on_start fires on key-down, on_stop on key-up. macOS auto-repeats key-down
    while held, so a _held flag dedupes."""

    def __init__(
        self,
        key_name: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ):
        self.key = getattr(keyboard.Key, key_name)
        self.on_start = on_start
        self.on_stop = on_stop
        self._held = False

    def _press(self, key) -> None:
        if key == self.key and not self._held:
            self._held = True
            self.on_start()

    def _release(self, key) -> None:
        if key == self.key and self._held:
            self._held = False
            self.on_stop()

    def run_forever(self) -> None:
        with keyboard.Listener(on_press=self._press, on_release=self._release) as listener:
            listener.join()


def is_hold_key(hotkey: str) -> bool:
    """A bare pynput Key name ('alt_l', 'f19') means hold mode; combos toggle."""
    return "+" not in hotkey and hasattr(keyboard.Key, hotkey)
