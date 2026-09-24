from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b"
    timeout_seconds: float = 3.0


class OllamaProvider:
    """ORION's local inference implementation using Ollama's HTTP API."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig()

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(self.config.base_url.rstrip("/") + path,
                                          data=json.dumps(payload).encode("utf-8"),
                                          headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def generate(self, prompt: str) -> str:
        result = self._request("/api/generate", {"model": self.config.model, "prompt": prompt, "stream": False})
        return str(result.get("response", ""))

    def embed(self, text: str) -> list[float]:
        result = self._request("/api/embed", {"model": self.config.model, "input": text})
        return [float(value) for value in result.get("embeddings", [[]])[0]]

    def analyze(self, data: Any) -> dict[str, Any]:
        return {"provider": "ollama", "response": self.generate("Analyze structured financial evidence as concise JSON: " + json.dumps(data, default=str))}
