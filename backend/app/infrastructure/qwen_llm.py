from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError


class QwenLLMClient:
    def __init__(self, base_url: str, model: str, timeout: float = 180.0) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    def generate_json(self, prompt: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Tu reponds uniquement en JSON valide."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1800,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Qwen LLM indisponible: {exc}") from exc
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return _loads_json(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ExternalServiceError("La reponse Qwen LLM n'est pas un JSON exploitable.") from exc


def get_llm_client(settings: Settings) -> QwenLLMClient:
    return QwenLLMClient(settings.llm_base_url, settings.llm_model)


def _loads_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(candidate[start:end + 1])
