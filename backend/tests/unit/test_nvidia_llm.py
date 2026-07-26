from __future__ import annotations

from typing import Any

from app.infrastructure.nvidia_llm import NvidiaLLMClient


class CapturingLLMClient(NvidiaLLMClient):
    def __init__(self) -> None:
        super().__init__(
            api_key="test-key",
            base_url="https://example.test/v1",
            model="model-under-test",
            timeout=10,
            max_retries=0,
            retry_delay=0,
            max_tokens=256,
            temperature=0,
            seed=0,
        )
        self.payload: dict[str, Any] | None = None

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = payload
        return {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}


class RetryingLLMClient(CapturingLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.max_retries = 1
        self.calls = 0

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            return {"choices": [{"message": {"content": "pas du json"}, "finish_reason": "stop"}]}
        return {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}


def test_generate_json_uses_deterministic_sampling_parameters() -> None:
    client = CapturingLLMClient()

    assert client.generate_json("Extract facts.") == {"ok": True}

    assert client.payload is not None
    assert client.payload["temperature"] == 0
    assert client.payload["top_p"] == 1
    assert client.payload["seed"] == 0
    assert client.payload["model"] == "model-under-test"


def test_generate_json_retries_invalid_json_response() -> None:
    client = RetryingLLMClient()

    assert client.generate_json("Extract facts.") == {"ok": True}
    assert client.calls == 2
