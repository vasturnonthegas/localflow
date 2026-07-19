import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class Config:
    model_size: str = "base"           # whisper model size
    stt_backend: str = "auto"          # auto | mlx | faster-whisper
    language: str | None = None        # None = autodetect
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    cleanup_enabled: bool = True
    # Bare pynput Key name ('alt_l' = left Option) = hold-to-talk;
    # GlobalHotKeys combo ('<cmd>+<shift>+<space>') = toggle.
    hotkey: str = "alt_l"
    sample_rate: int = 16000
    server_host: str = "0.0.0.0"
    server_port: int = 8756
    # Meeting transcription -> Obsidian
    vault_path: str = "~/Documents/ObsidianVault"
    notes_folder: str = "Transcription Notes"
    logs_folder: str = "Transcription Logs"
    meeting_watch: bool = True         # detect mic-in-use and notify
    meeting_chunk_seconds: int = 30    # transcribe in chunks of this length
    meeting_min_busy_seconds: int = 12 # sustained mic use before "meeting detected"
    # Work-prompt extraction from meeting notes (open-weights model on Fireworks).
    # Key comes from FIREWORKS_API_KEY env var or fireworks_api_key here.
    work_prompts: bool = True
    fireworks_api_key: str = ""
    fireworks_model: str = "accounts/fireworks/models/kimi-k2p6"


def load_config() -> Config:
    """Read ~/.localflow.toml (tomllib) if present, override defaults; missing file OK."""
    config = Config()
    path = Path.home() / ".localflow.toml"
    if not path.exists():
        return config

    with path.open("rb") as f:
        data = tomllib.load(f)

    known_keys = {f.name for f in fields(Config)}
    for key, value in data.items():
        if key in known_keys:
            setattr(config, key, value)

    return config
