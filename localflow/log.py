import logging
from pathlib import Path

LOG_PATH = Path.home() / ".localflow" / "localflow.log"


def setup_logging() -> Path:
    """File logger at ~/.localflow/localflow.log; console keeps the terse prints."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_PATH)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger("localflow")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    return LOG_PATH
