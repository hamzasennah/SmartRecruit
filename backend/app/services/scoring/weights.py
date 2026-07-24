import json
from functools import lru_cache

from app.config import settings

DEFAULT_WEIGHTS = {
    "technical_skills": 0.33,
    "experience": 0.28,
    "responsibilities": 0.14,
    "education": 0.10,
    "languages": 0.05,
    "certifications_domains": 0.10,
    "soft_skills": 0.0,
}


@lru_cache(maxsize=1)
def load_scoring_weights() -> dict[str, float]:
    path = settings.data_dir / "scoring_weights.json"
    weights = json.loads(path.read_text(encoding="utf-8")) if path.exists() else DEFAULT_WEIGHTS
    total = sum(float(v) for v in weights.values()) or 1.0
    return {k: float(v) / total for k, v in weights.items()}

