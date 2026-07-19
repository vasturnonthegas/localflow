import numpy as np

_MLX_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


class Transcriber:
    """STT front-end. backend='auto' uses mlx-whisper (Apple GPU) when installed
    and the model size has an MLX build, else falls back to faster-whisper CPU int8.
    Measured on M-series: MLX small 951ms vs CPU small 3202ms on a 13.8s clip."""

    def __init__(
        self,
        model_size: str = "small",
        language: str | None = None,
        backend: str = "auto",
    ):
        self.language = language
        self.model_size = model_size
        self._mlx = None
        self.model = None

        if backend not in ("auto", "mlx", "faster-whisper"):
            raise ValueError(f"unknown stt backend: {backend!r}")

        if backend in ("auto", "mlx") and model_size in _MLX_REPOS:
            try:
                import mlx_whisper

                self._mlx = mlx_whisper
                self._mlx_repo = _MLX_REPOS[model_size]
                # Trigger model download/load now, not on first dictation.
                mlx_whisper.transcribe(
                    np.zeros(1600, dtype=np.float32), path_or_hf_repo=self._mlx_repo
                )
                self.backend = "mlx"
                return
            except ImportError:
                if backend == "mlx":
                    raise

        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.backend = "faster-whisper"

    def transcribe(self, audio: "np.ndarray") -> str:
        """audio: 1-D float32 16kHz. Return joined stripped text."""
        if self._mlx is not None:
            result = self._mlx.transcribe(
                audio, path_or_hf_repo=self._mlx_repo, language=self.language
            )
            return result["text"].strip()
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
