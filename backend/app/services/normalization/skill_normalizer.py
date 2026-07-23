from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.services.normalization.text_normalizer import dedupe_preserve_order, normalize_text


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    path = settings.data_dir / "skill_aliases.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {normalize_text(key): normalize_text(value) for key, value in data.items()}


def normalize_skill(skill: str | None) -> str:
    normalized = normalize_text(skill)
    return _aliases().get(normalized, normalized)


def normalize_skill_list(skills: list[str]) -> list[str]:
    return dedupe_preserve_order([normalize_skill(skill) for skill in skills])


def aliases_for_skill(skill: str | None) -> list[str]:
    canonical = normalize_skill(skill)
    aliases = [alias for alias, target in _aliases().items() if target == canonical]
    return dedupe_preserve_order([canonical, *aliases])

