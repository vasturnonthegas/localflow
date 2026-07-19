"""Convert spoken symbol names in dictated text to the symbols themselves.

"config slash settings dash prod underscore v2" -> "config/settings-prod_v2"
Dictation-only: meeting transcripts keep natural speech untouched.
"""

import re

# Glue both sides: "warm dash cache" -> "warm-cache"
_JOINING = {
    "dash": "-",
    "hyphen": "-",
    "underscore": "_",
}

# Word possibly wrapped in whisper punctuation, e.g. " dash," or "Dash."
_JOIN_PATTERN = re.compile(
    r"\s*\b(" + "|".join(_JOINING) + r")\b[.,]?\s*",
    re.IGNORECASE,
)

# Slash binds rightward only, so dictated slash-commands keep the space
# before them: "run slash skill" -> "run /skill". A slash directly after
# another symbol or start of text gets no leading space: "slash home" -> "/home".
_SLASH_PATTERN = re.compile(r"(^|\s+)slash\b[.,]?\s*", re.IGNORECASE)


def apply_spoken_symbols(text: str) -> str:
    text = _JOIN_PATTERN.sub(lambda m: _JOINING[m.group(1).lower()], text)
    text = _SLASH_PATTERN.sub(lambda m: ("/" if m.group(1) == "" else " /"), text)
    return text
