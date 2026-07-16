from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ExternalServiceError


logger = logging.getLogger(__name__)


class NvidiaLLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        retry_delay: float,
        max_tokens: int,
        temperature: float,
    ) -> None:
        if not api_key:
            raise ExternalServiceError("NVIDIA_API_KEY est obligatoire pour appeler le modele NVIDIA.")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only. No markdown, no comments, no explanation. "
                        "Use null for unknown strings and [] for unknown arrays."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        response = self._post("/chat/completions", payload)
        try:
            content = response["choices"][0]["message"]["content"]
            return _loads_json(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ExternalServiceError("La reponse NVIDIA LLM n'est pas un JSON exploitable.") from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA LLM tentative %s/%s echouee avec HTTP %s.",
                        attempt,
                        self.max_retries + 1,
                        response.status_code,
                    )
                    time.sleep(self.retry_delay)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt <= self.max_retries:
                    logger.warning(
                        "NVIDIA LLM tentative %s/%s echouee: %s",
                        attempt,
                        self.max_retries + 1,
                        exc,
                    )
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError(f"NVIDIA LLM indisponible: {last_error}") from last_error


def get_llm_client(settings: Settings) -> NvidiaLLMClient:
    return NvidiaLLMClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        retry_delay=settings.llm_retry_delay,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )


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
