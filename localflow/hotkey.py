import logging
from collections.abc import Callable

from pynput import keyboard

log = logging.getLogger("localflow.hotkey")


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
        self._saw_any_event = False

    def _note_event(self) -> None:
        # First event of any kind proves Input Monitoring permission works;
        # we log only that fact, never which keys were typed.
        if not self._saw_any_event:
            self._saw_any_event = True
            log.info("first keyboard event received — Input Monitoring OK")

    def _press(self, key) -> None:
        self._note_event()
        if key == self.key and not self._held:
            self._held = True
            log.debug("hotkey down")
            try:
                self.on_start()
            except Exception:
                log.exception("on_start failed")

    def _release(self, key) -> None:
        self._note_event()
        if key == self.key and self._held:
            self._held = False
            log.debug("hotkey up")
            try:
                self.on_stop()
            except Exception:
                log.exception("on_stop failed")

    def run_forever(self) -> None:
        log.info("HoldKeyListener starting for key=%s", self.key)
        with keyboard.Listener(on_press=self._press, on_release=self._release) as listener:
            listener.join()
        log.warning("keyboard listener exited")


def is_hold_key(hotkey: str) -> bool:
    """A bare pynput Key name ('alt_l', 'f19') means hold mode; combos toggle."""
    return "+" not in hotkey and hasattr(keyboard.Key, hotkey)
