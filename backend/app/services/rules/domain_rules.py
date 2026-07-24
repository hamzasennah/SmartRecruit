from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import settings


@lru_cache(maxsize=1)
def load_domain_rules() -> dict[str, Any]:
    path = settings.data_dir / "domain_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_domain_rule_section(section: str) -> dict[str, Any]:
    value = load_domain_rules().get(section, {})
    return value if isinstance(value, dict) else {}
