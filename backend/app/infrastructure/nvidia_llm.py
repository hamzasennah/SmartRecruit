from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import Settings
from app.core.exceptions import ExternalServiceError, OutputValidationError
from app.infrastructure.nvidia_client import NvidiaAPIClient
from app.services.extraction.output_validator import parse_json_payload

logger = logging.getLogger(__name__)


class NvidiaLLMClient(NvidiaAPIClient):
    call_type = "llm"
    missing_api_key_message = "NVIDIA_API_KEY est obligatoire pour appeler le modele NVIDIA."
    retry_log_label = "NVIDIA LLM"
    unavailable_error_prefix = "NVIDIA LLM indisponible"

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
        seed: int | None = 0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            logger=logger,
        )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed

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
            "top_p": 1,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        last_error: Exception | None = None
        for parse_attempt in range(1, self.max_retries + 2):
            response = self._post("/chat/completions", payload)
            try:
                content = response["choices"][0]["message"]["content"]
                return _loads_json(content)
            except (KeyError, IndexError, TypeError) as exc:
                raise ExternalServiceError("La reponse NVIDIA LLM n'a pas le format attendu.") from exc
            except (json.JSONDecodeError, OutputValidationError) as exc:
                last_error = exc
                finish_reason = _finish_reason(response)
                preview = str(content)[-600:]
                logger.error(
                    "JSON NVIDIA invalide. tentative=%s/%s, finish_reason=%s, longueur=%s, fin_reponse=%r",
                    parse_attempt,
                    self.max_retries + 1,
                    finish_reason,
                    len(str(content)),
                    preview,
                )
                if finish_reason == "length":
                    raise ExternalServiceError(
                        "La reponse NVIDIA LLM est tronquee. Augmentez NVIDIA_MAX_TOKENS dans .env."
                    ) from exc
                if parse_attempt <= self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                break
        raise ExternalServiceError("La reponse NVIDIA LLM n'est pas un JSON exploitable.") from last_error

    def _input_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "message_count": len(payload.get("messages", [])),
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "seed": payload.get("seed"),
        }


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
        seed=settings.llm_seed,
    )


def _loads_json(text: str) -> dict[str, Any]:
    return parse_json_payload(text)


def _finish_reason(response: dict[str, Any]) -> str | None:
    try:
        return response["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return None
