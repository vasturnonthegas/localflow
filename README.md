# localflow

Local push-to-talk dictation for macOS. Fully offline STT using Whisper (faster-whisper), optional LLM cleanup, and phone access via Tailscale.

## What it is

An open-source WisprFlow-style dictation app:
- **Hold left Option** (default) to record — release to transcribe and paste; combo hotkeys toggle instead
- **Offline transcription** via faster-whisper (no cloud calls)
- **Optional cleanup** with Ollama (fix punctuation, casing, remove filler words)
- **Instant paste** into the frontmost app
- **Server mode** for phone access: record in browser over HTTPS (Tailscale), get transcript, copy to clipboard

## Requirements

- **macOS** (10.13+)
- **Python 3.11+**
- **ffmpeg** (via Homebrew: `brew install ffmpeg`)
- **Ollama** (optional, for cleanup): `ollama pull llama3.2:3b`

## Install

```bash
git clone <repo> && cd localflow
./setup.sh
```

Or manually:
```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Usage

### Desktop app (local dictation)

```bash
localflow
```

- **Hold left Option**, speak, release — transcript pastes. Customize in `~/.localflow.toml`
- Text pastes into your frontmost app
- Run from terminal; watch for model download (~1s first run) and transcription timing

### Menu bar (hub)

```bash
lf menubar
```

Runs a status-bar app that is the control center for both dictation and
meetings — no terminal needed:

- **Live status icon** — 🎙 idle, 🔴 recording, ⏳ transcribing, 🎙❗ meeting
  detected, 🎙⚫ nothing running. The dictation app publishes its state to
  `~/.localflow/dictation.json`, which the menu bar reads (so this works even
  when the server is off).
- **Recent dictations** submenu — click any of the last 10 transcripts to
  re-copy it to the clipboard.
- **Start/Stop dictation** and **Start localflow server** — launch either
  component directly from the menu.
- Meeting detection, live session control, and links to the web UI / notes
  folder.

### macOS permissions

Grant on first run:
1. **Microphone**: System Settings → Privacy & Security → Microphone → Terminal (or your app launcher)
2. **Accessibility**: System Settings → Privacy & Security → Accessibility → Terminal (for paste injection)

### Configuration

Create `~/.localflow.toml`:

```toml
model_size = "base"               # whisper model: tiny, base, small, medium, large-v3
stt_backend = "auto"              # auto | mlx | faster-whisper
# language = "en"                 # omit for autodetect
cleanup_enabled = true
ollama_url = "http://localhost:11434"
ollama_model = "llama3.2:3b"
hotkey = "alt_l"                  # bare key name = hold-to-talk; "<cmd>+<shift>+<space>" = toggle
sample_rate = 16000
server_host = "0.0.0.0"
server_port = 8756
```

All keys are optional; defaults shown above apply.

### Phone access (Tailscale)

#### Setup

1. On **Mac**:
   ```bash
   localflow-server
   ```
   Server starts on http://0.0.0.0:8756 (config.server_port).

2. Install **Tailscale** on Mac and phone:
   - macOS: `brew install tailscale` → `tailscale up`
   - iOS: App Store → sign in with same account

3. On **Mac**, expose the server over HTTPS:
   ```bash
   tailscale serve --bg 8756
   ```
   Tailscale prints an HTTPS URL (e.g., `https://myhost.example.ts.net`).

4. On **phone**, open that URL in browser:
   - Large record/stop button
   - Speak, hit stop
   - Transcript appears
   - Tap copy-to-clipboard

#### iOS Shortcut (alternative)

Create a Shortcut that POSTs audio to `/transcribe`:

```
1. Ask for audio
2. POST [HTTPS URL]/transcribe (multipart form: file parameter)
3. Parse JSON response: {"text": ..., "ms": ...}
4. Show text
```

## Troubleshooting

### Microphone blocked on HTTP

- **Symptom**: "NotAllowedError: Permission denied" in browser on phone
- **Fix**: Use Tailscale (HTTPS required; see Setup above). Localhost works on desktop but not from phone.

### First run is slow

- **Symptom**: 5–30s delay before recording starts
- **Cause**: faster-whisper downloads the model (~1–3 GB depending on model_size)
- **Fix**: Check console; subsequent runs are fast (~100–500ms transcription per 10s audio)

### Ollama cleanup unavailable

- **Symptom**: Text doesn't get cleaned; appears in raw transcript
- **Cause**: Ollama service not running or model not pulled
- **Fix**: 
  - `ollama serve` in another terminal
  - `ollama pull llama3.2:3b` (or your configured model)
  - If unavailable, raw transcript is returned (no error; graceful fallback)

### Paste doesn't work

- **Symptom**: Text recorded and transcribed but not pasted
- **Cause**: Missing Accessibility permission
- **Fix**: System Settings → Privacy & Security → Accessibility → add Terminal/your launcher

## Architecture

- **localflow/config.py**: Load ~/.localflow.toml (TOML parsing)
- **localflow/audio.py**: Record mono float32 via sounddevice
- **localflow/stt.py**: Transcribe via faster-whisper (CPU, int8 quantization)
- **localflow/cleanup.py**: Optional Ollama LLM polish (timeout 15s, graceful fallback)
- **localflow/inject.py**: Paste text via osascript and System Events
- **localflow/hotkey.py**: Global hotkey listener (pynput)
- **localflow/app.py**: Desktop CLI entrypoint
- **localflow/server.py**: FastAPI web server for phone access
- **localflow/static/index.html**: Single-page mobile app (no external assets)
