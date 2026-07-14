from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.services.normalization.text_normalizer import normalize_text


@lru_cache(maxsize=1)
def education_levels() -> dict[str, int]:
    path = settings.data_dir / "education_levels.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {normalize_text(key): int(value) for key, value in data.items()}


def normalize_education_level(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    if normalized in education_levels():
        return normalized
    for level in sorted(education_levels(), key=len, reverse=True):
        if level in normalized:
            return level
    return normalized


def education_rank(value: str | None) -> int:
    level = normalize_education_level(value)
    return education_levels().get(level or "", 0)

