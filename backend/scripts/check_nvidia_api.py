from __future__ import annotations

import sys

import httpx

from app.config import settings


def _headers() -> dict[str, str]:
    if not settings.nvidia_api_key:
        raise RuntimeError("NVIDIA_API_KEY est obligatoire dans .env.")
    return {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def main() -> None:
    headers = _headers()
    timeout = settings.llm_timeout

    models_response = httpx.get(
        f"{settings.nvidia_base_url}/models",
        headers=headers,
        timeout=timeout,
    )
    models_response.raise_for_status()
    print("NVIDIA /models: OK")

    chat_response = httpx.post(
        f"{settings.nvidia_base_url}/chat/completions",
        headers=headers,
        json={
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": "Return exactly {\"ok\": true}."},
            ],
            "temperature": 0,
            "max_tokens": 30,
        },
        timeout=timeout,
    )
    chat_response.raise_for_status()
    print("NVIDIA chat/completions: OK")

    embedding_response = httpx.post(
        f"{settings.embedding_base_url}/embeddings",
        headers=headers,
        json={
            "model": settings.embedding_model,
            "input": ["Data analyst avec Power BI, SQL et tableaux de bord."],
        },
        timeout=timeout,
    )
    embedding_response.raise_for_status()
    vector = embedding_response.json()["data"][0]["embedding"]
    print(f"NVIDIA embeddings: OK ({len(vector)} dimensions)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Echec NVIDIA API: {exc}", file=sys.stderr)
        raise
