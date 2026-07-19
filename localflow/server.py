import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from localflow.cleanup import Cleaner
from localflow.config import load_config
from localflow.stt import Transcriber

app = FastAPI()

_config = load_config()
_transcriber: Transcriber | None = None
_cleaner: Cleaner | None = None
_lock = threading.Lock()

_STATIC_DIR = Path(__file__).parent / "static"


def _get_transcriber() -> Transcriber:
    global _transcriber
    if _transcriber is None:
        with _lock:
            if _transcriber is None:
                _transcriber = Transcriber(
                    model_size=_config.model_size, language=_config.language
                )
    return _transcriber


def _get_cleaner() -> Cleaner:
    global _cleaner
    if _cleaner is None:
        with _lock:
            if _cleaner is None:
                _cleaner = Cleaner(url=_config.ollama_url, model=_config.ollama_model)
    return _cleaner


def _decode_audio(data: bytes) -> np.ndarray:
    try:
        proc = _run_ffmpeg(data)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500, detail="ffmpeg not installed (brew install ffmpeg)"
        )
    if proc.returncode != 0 or not proc.stdout:
        stderr = proc.stderr.decode(errors="replace").strip()
        message = stderr.splitlines()[-1] if stderr else "ffmpeg failed to decode audio"
        raise HTTPException(status_code=400, detail=message[:300])
    return np.frombuffer(proc.stdout, dtype=np.float32)


def _run_ffmpeg(data: bytes) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "ffmpeg",
            "-i", "pipe:0",
            "-f", "f32le",
            "-ac", "1",
            "-ar", "16000",
            "pipe:1",
        ],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _transcribe_sync(audio: np.ndarray, clean: bool) -> str:
    text = _get_transcriber().transcribe(audio)
    if clean:
        text = _get_cleaner().clean(text)
    return text


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/transcribe")
async def transcribe(file: UploadFile, clean: int = 0) -> dict:
    start = time.monotonic()
    data = await file.read()
    audio = await run_in_threadpool(_decode_audio, data)
    if audio.size == 0:
        raise HTTPException(status_code=400, detail="decoded audio is empty")
    text = await run_in_threadpool(_transcribe_sync, audio, bool(clean))
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {"text": text, "ms": elapsed_ms}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=_config.server_host, port=_config.server_port)


if __name__ == "__main__":
    main()
