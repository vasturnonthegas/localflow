import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from localflow import sounds
from localflow.cleanup import Cleaner
from localflow.config import load_config
from localflow.log import setup_logging
from localflow.meetings import (
    MeetingSession,
    MeetingSummarizer,
    MeetingWatcher,
    ObsidianWriter,
)
from localflow.stt import Transcriber
from localflow.symbols import apply_spoken_symbols
from localflow.workprompts import WorkPromptGenerator

app = FastAPI()

setup_logging()
_config = load_config()
_transcriber: Transcriber | None = None
_cleaner: Cleaner | None = None
_lock = threading.Lock()
_transcribe_lock = threading.Lock()

_watcher = MeetingWatcher(
    min_busy_seconds=_config.meeting_min_busy_seconds,
)
_session: MeetingSession | None = None
_session_meta: dict = {}
_last_saved: dict | None = None
_summarizer = MeetingSummarizer(_config.ollama_url, _config.ollama_model)
_writer = ObsidianWriter(
    _config.vault_path, _config.notes_folder, _config.logs_folder
)
_prompt_gen = WorkPromptGenerator(
    model=_config.fireworks_model, api_key=_config.fireworks_api_key
)


@app.on_event("startup")
def _start_watcher() -> None:
    if _config.meeting_watch:
        _watcher.start()

_STATIC_DIR = Path(__file__).parent / "static"


def _get_transcriber() -> Transcriber:
    global _transcriber
    if _transcriber is None:
        with _lock:
            if _transcriber is None:
                _transcriber = Transcriber(
                    model_size=_config.model_size,
                    language=_config.language,
                    backend=_config.stt_backend,
                )
    return _transcriber


def _get_cleaner() -> Cleaner:
    global _cleaner
    if _cleaner is None:
        with _lock:
            if _cleaner is None:
                _cleaner = Cleaner(
                    url=_config.ollama_url,
                    model=_config.ollama_model,
                    timeout=_config.cleanup_timeout,
                    num_ctx=_config.cleanup_num_ctx,
                )
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
    if _config.spoken_symbols and text:
        text = apply_spoken_symbols(text)
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


class MeetingStart(BaseModel):
    title: str = "Meeting"
    category: str = ""


@app.get("/meeting/status")
def meeting_status() -> dict:
    session = _session
    live = None
    if session is not None and session.active:
        live = {
            "title": _session_meta.get("title", "Meeting"),
            "category": _session_meta.get("category", "Other"),
            "seconds": int(session.elapsed_seconds()),
            "segments": [
                {"stamp": s.stamp, "text": s.text} for s in session.segments[-8:]
            ],
            "segment_count": len(session.segments),
        }
    return {
        "watching": _watcher.error == "" and _config.meeting_watch,
        "watch_error": _watcher.error,
        "mic_busy": _watcher.mic_busy,
        "detected": _watcher.detected,
        "platform": _watcher.platform,
        "session": live,
        "last_saved": _last_saved,
    }


@app.post("/meeting/start")
def meeting_start(body: MeetingStart) -> dict:
    global _session, _session_meta, _last_saved
    if _session is not None and _session.active:
        raise HTTPException(status_code=409, detail="a meeting session is already running")
    category = body.category or _watcher.platform or "Other"
    session = MeetingSession(
        _get_transcriber(),
        _transcribe_lock,
        sample_rate=_config.sample_rate,
        chunk_seconds=_config.meeting_chunk_seconds,
    )
    _watcher.pause()  # we hold the mic now; don't self-detect
    try:
        session.start()
    except Exception as exc:
        _watcher.resume()
        raise HTTPException(status_code=500, detail=f"mic open failed: {exc}")
    _session = session
    _session_meta = {"title": body.title or "Meeting", "category": category}
    _last_saved = None
    if _config.sounds_enabled:
        sounds.play("start")
    return {"ok": True, "category": category}


@app.post("/meeting/stop")
async def meeting_stop() -> dict:
    global _session, _last_saved
    session = _session
    if session is None or not session.active:
        raise HTTPException(status_code=409, detail="no meeting session running")

    def _finish() -> dict:
        global _last_saved
        segments = session.stop()
        if _config.sounds_enabled:
            sounds.play("stop")
        _watcher.resume()
        transcript = " ".join(s.text for s in segments)
        notes_md = _summarizer.summarize(transcript)
        if _config.work_prompts:
            prompts_md = _prompt_gen.generate(notes_md)
            if prompts_md:
                notes_md += f"\n\n## Suggested Work Prompts\n\n{prompts_md}"
        saved = _writer.write(
            title=_session_meta.get("title", "Meeting"),
            category=_session_meta.get("category", "Other"),
            started_at=session.started_at,
            duration_seconds=session.elapsed_seconds(),
            notes_md=notes_md,
            segments=segments,
        )
        _last_saved = {
            "notes_path": str(saved.notes_path),
            "log_path": str(saved.log_path),
            "segments": len(segments),
        }
        return _last_saved

    result = await run_in_threadpool(_finish)
    _session = None
    return result


@app.post("/meeting/dismiss")
def meeting_dismiss() -> dict:
    _watcher.dismiss()
    return {"ok": True}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=_config.server_host, port=_config.server_port)


if __name__ == "__main__":
    main()
