from __future__ import annotations

import re
from typing import Any


def coerce_string_list(value: Any, preferred_keys: tuple[str, ...] = ("value", "name", "text")) -> list[str]:
    # LLMs sometimes return a scalar or object where the schema expects a list;
    # coercion keeps extraction robust while validation still owns final shape.
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return [str(value)]
    result: list[str] = []
    for item in value:
        scalar = coerce_scalar(item, preferred_keys)
        if scalar:
            result.append(scalar)
    return result


def coerce_scalar(value: Any, preferred_keys: tuple[str, ...] = ("value", "name", "text")) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Prefer semantically named keys before falling back to any string value;
        # this reduces accidental selection from noisy model objects.
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None
    return str(value)


def coerce_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else default


def coerce_year(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None

# Role dans le projet:
# Ce fichier nettoie les formes imparfaites renvoyees par le LLM. Les extracteurs l'appellent avant validation Pydantic.
