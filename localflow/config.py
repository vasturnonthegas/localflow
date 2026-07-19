import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class Config:
    model_size: str = "small"          # faster-whisper model
    language: str | None = None        # None = autodetect
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    cleanup_enabled: bool = True
    hotkey: str = "<cmd>+<shift>+<space>"   # pynput GlobalHotKeys format
    sample_rate: int = 16000
    server_host: str = "0.0.0.0"
    server_port: int = 8756


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
