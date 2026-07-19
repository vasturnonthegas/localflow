import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str = "small", language: str | None = None):
        """faster-whisper WhisperModel, device='cpu', compute_type='int8'. Load once."""
        self.language = language
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio: "np.ndarray") -> str:
        """audio: 1-D float32 16kHz. Use vad_filter=True. Return joined stripped text."""
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
