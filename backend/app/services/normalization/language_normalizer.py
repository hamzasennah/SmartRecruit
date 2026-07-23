from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.services.normalization.text_normalizer import normalize_text

LANGUAGE_ALIASES = {"french": "francais", "francais": "francais", "english": "anglais", "anglais": "anglais", "arabic": "arabe", "arabe": "arabe"}
LEVEL_ALIASES = {
    "anglais professionnel": "professional",
    "capacite professionnelle complete": "professional",
    "courante": "courant",
    "maternelle": "native",
    "maternel": "native",
    "niveau professionnel": "professional",
    "professionnelle": "professional",
    "professionnel": "professional",
}


@lru_cache(maxsize=1)
def language_levels() -> dict[str, int]:
    path = settings.data_dir / "language_levels.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {normalize_text(key): int(value) for key, value in data.items()}


def normalize_language(value: str | None) -> str:
    normalized = normalize_text(value)
    return LANGUAGE_ALIASES.get(normalized, normalized)


def normalize_language_level(value: str | None) -> str | None:
    normalized = normalize_text(value)
    return LEVEL_ALIASES.get(normalized, normalized) or None


def language_rank(value: str | None) -> int:
    return language_levels().get(normalize_language_level(value) or "", 0)

