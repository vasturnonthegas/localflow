from collections.abc import Callable

from pynput import keyboard


class HotkeyListener:
    def __init__(self, combo: str, on_toggle: Callable[[], None]):
        self.combo = combo
        self.on_toggle = on_toggle

    def run_forever(self) -> None:
        with keyboard.GlobalHotKeys({self.combo: self.on_toggle}) as listener:
            listener.join()
