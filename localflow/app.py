import queue
import threading
import time

import numpy as np

from localflow.audio import Recorder
from localflow.cleanup import Cleaner
from localflow.config import load_config
from localflow.hotkey import HotkeyListener
from localflow.inject import paste_text
from localflow.stt import Transcriber

MIN_CLIP_SECONDS = 0.3


def _print_banner(config) -> None:
    print("=" * 60)
    print("localflow — local push-to-talk dictation")
    print("=" * 60)
    print(f"  hotkey:       {config.hotkey}")
    print(f"  model:        {config.model_size}")
    print(f"  ollama model: {config.ollama_model}")
    print("-" * 60)
    print("macOS permissions required for this terminal app:")
    print("  System Settings -> Privacy & Security -> Microphone")
    print("  System Settings -> Privacy & Security -> Accessibility")
    print("=" * 60)


def main() -> None:
    """Desktop entrypoint (console script `localflow`)."""
    config = load_config()

    print("loading model…")
    transcriber = Transcriber(model_size=config.model_size, language=config.language)
    recorder = Recorder(sample_rate=config.sample_rate)
    cleaner = Cleaner(config.ollama_url, config.ollama_model)

    work_queue: "queue.Queue[np.ndarray]" = queue.Queue()

    def worker() -> None:
        while True:
            audio = work_queue.get()
            if audio is None:
                break
            _process_clip(audio, config, transcriber, cleaner)
            work_queue.task_done()

    worker_thread = threading.Thread(target=worker, daemon=True)
    worker_thread.start()

    def on_toggle() -> None:
        if not recorder.recording:
            recorder.start()
            print("● recording")
        else:
            audio = recorder.stop()
            print("■ transcribing…")
            duration = len(audio) / config.sample_rate if config.sample_rate else 0
            if duration < MIN_CLIP_SECONDS:
                return
            work_queue.put(audio)

    _print_banner(config)

    listener = HotkeyListener(config.hotkey, on_toggle)
    try:
        listener.run_forever()
    except KeyboardInterrupt:
        print("\nexiting…")


def _process_clip(audio: np.ndarray, config, transcriber: Transcriber, cleaner: Cleaner) -> None:
    start = time.monotonic()
    text = transcriber.transcribe(audio)
    if config.cleanup_enabled and text:
        text = cleaner.clean(text)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if text:
        paste_text(text)
        print(f"{text}  ({elapsed_ms}ms)")


if __name__ == "__main__":
    main()
