from __future__ import annotations

import json
from functools import lru_cache

from app.config import settings
from app.services.normalization.text_normalizer import normalize_text


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    path = settings.data_dir / "job_title_aliases.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {normalize_text(key): normalize_text(value) for key, value in data.items()}


def normalize_job_title(title: str | None) -> str:
    normalized = normalize_text(title)
    return _aliases().get(normalized, normalized)

