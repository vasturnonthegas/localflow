# localflow — progress

Open-source WisprFlow clone: local push-to-talk dictation on macOS.
Stack: faster-whisper (STT, int8 CPU) · Ollama llama3.2:3b (cleanup) · pynput hotkey · clipboard paste · FastAPI + Tailscale for phone.

## Status: v0.1.0 — working end-to-end (2026-07-18)

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
- CPU int8 whisper, not mlx-whisper — swap inside `stt.py` only if `small` feels slow on Apple Silicon

### Ideas / later
- [ ] mlx-whisper backend for Apple Silicon speed
- [ ] Per-app vocabulary hints / custom prompt for cleanup model
- [ ] History file of past dictations
