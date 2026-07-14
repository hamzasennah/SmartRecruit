import json
import re
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def parse_json_payload(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def validate_model(raw: str | dict, model: type[T]) -> T:
    return model.model_validate(parse_json_payload(raw) if isinstance(raw, str) else raw)
