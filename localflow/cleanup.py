import requests

_SYSTEM_PROMPT = (
    "You are a strict text cleanup tool. Fix punctuation and casing, and remove "
    "filler words (um, uh). Do NOT change wording or meaning, do NOT add or remove "
    "any information, do NOT rephrase. Return only the cleaned text with no "
    "commentary, no quotes, and no explanations."
)


class Cleaner:
    def __init__(
        self,
        url: str,
        model: str,
        timeout: int = 120,
        num_ctx: int = 8192,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx

    def clean(self, text: str) -> str:
        try:
            prompt = f"{_SYSTEM_PROMPT}\n\nText:\n{text}"
            resp = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    # Long dictations need a big context and no output cap,
                    # else Ollama truncates the cleaned text.
                    "options": {"num_ctx": self.num_ctx, "num_predict": -1},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            cleaned = data.get("response", "")
            cleaned = cleaned.strip().strip('"').strip("'").strip()
            if not cleaned:
                return text
            return cleaned
        except Exception:
            return text
