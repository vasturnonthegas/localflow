# localflow — progress

Open-source WisprFlow clone: local push-to-talk dictation on macOS.
Stack: faster-whisper (STT, int8 CPU) · Ollama llama3.2:3b (cleanup) · pynput hotkey · clipboard paste · FastAPI + Tailscale for phone.

## Status: v0.2.0 — MLX backend, 3.4x faster STT (2026-07-18)

### Perf (13.8s speech clip, M-series)
| Backend | Model | Latency |
|---|---|---|
| faster-whisper CPU int8 | small | 3202ms |
| faster-whisper CPU int8 | base | 989ms |
| **mlx-whisper (GPU)** | **small** | **951ms** |
| mlx-whisper (GPU) | base | 337ms |

Default: `stt_backend = "auto"` → MLX when installed, faster-whisper fallback.
Rust rewrite evaluated and rejected: inference is native code either way, Python glue is single-digit ms.

### Done
- [x] Core modules: `audio.py` (thread-safe recorder), `stt.py` (faster-whisper), `cleanup.py` (Ollama, silent fallback to raw transcript), `inject.py` (clipboard paste + restore), `hotkey.py` (⌘⇧Space toggle), `app.py` (worker-thread pipeline), `config.py` (`~/.localflow.toml`)
- [x] Phone path: `server.py` (POST /transcribe, ffmpeg decode, GET /healthz) + mobile web page (`static/index.html`, MediaRecorder, copy button)
- [x] Docs: README (install, permissions, Tailscale phone setup, iOS Shortcut alternative), setup.sh
- [x] Environment: Python 3.12 + ffmpeg installed via brew, venv built, `pip install -e .` clean
- [x] Verified: smoke test (config/endpoints/Ollama-fallback) green; end-to-end `say`-generated speech → `/transcribe` → exact text back; garbage input → clean 400
- [x] Bugfix: missing ffmpeg crashed server with raw traceback → now clean 500 with install hint

### Not yet done
- [ ] Live test on real mic + real Ollama cleanup (needs `ollama pull llama3.2:3b`)
- [ ] macOS permissions walkthrough confirmed on this machine (Microphone + Accessibility)
- [ ] Tailscale serve tested from actual phone
- [ ] Menu bar app wrapper (currently terminal process)
- [ ] Launch-at-login (launchd plist)

### Deliberate scope cuts
- No word-by-word streaming partials — push-to-talk UX matches WisprFlow, streaming adds big complexity for little dictation value
### Done in v0.2.0
- [x] mlx-whisper backend (`stt.py`), `stt_backend` config key, `pip install -e '.[mlx]'`
- [x] Skip Ollama cleanup for clips under 5 words
- [x] Benchmarked small/base on both backends (table above)

### Ideas / later
- [ ] Per-app vocabulary hints / custom prompt for cleanup model
- [ ] History file of past dictations
