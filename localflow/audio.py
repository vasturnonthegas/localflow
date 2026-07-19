import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger("localflow.audio")


class Recorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._recording = False

    def _callback(self, indata, frames, time, status) -> None:
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

    def start(self) -> None:
        """Begin capturing mono float32 from default mic via sounddevice.InputStream."""
        with self._lock:
            self._chunks = []
        try:
            device = sd.query_devices(kind="input")
            log.info("opening input stream on device: %s", device.get("name"))
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            log.exception("failed to open mic input stream")
            raise
        self._recording = True
        log.info("recording started")

    def stop(self) -> np.ndarray:
        """Stop capture, return full clip as 1-D float32 np array at sample_rate."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._recording = False
        with self._lock:
            if self._chunks:
                audio = np.concatenate(self._chunks)
            else:
                audio = np.array([], dtype=np.float32)
            self._chunks = []
        log.info(
            "recording stopped: %.2fs captured, peak amplitude %.4f",
            len(audio) / self.sample_rate,
            float(np.abs(audio).max()) if len(audio) else 0.0,
        )
        return audio.astype(np.float32)

    @property
    def recording(self) -> bool:
        return self._recording
