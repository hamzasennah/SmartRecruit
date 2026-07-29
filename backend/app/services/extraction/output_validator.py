import json
import re
from typing import TypeVar

from pydantic import BaseModel

from app.core.exceptions import OutputValidationError

T = TypeVar("T", bound=BaseModel)


def parse_json_payload(raw: str) -> dict:
    candidates = _json_candidates(raw)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            raise OutputValidationError("La reponse NVIDIA LLM doit etre un objet JSON.")
        return payload
    raise OutputValidationError("La reponse NVIDIA LLM n'est pas un JSON exploitable.")


def validate_model(raw: str | dict, model: type[T]) -> T:
    return model.model_validate(parse_json_payload(raw) if isinstance(raw, str) else raw)


def _json_candidates(raw: str) -> list[str]:
    text = raw.strip()
    candidates: list[str] = []

    # The prompt asks for JSON only, but model responses can still include code
    # fences; candidates are tried from strictest to most forgiving.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.append(fenced.group(1).strip())

    if text.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
        candidates.append(stripped)

    candidates.append(text)

    balanced = _extract_balanced_json_object(text)
    if balanced:
        candidates.append(balanced)

    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _extract_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        # Balanced extraction respects strings and escapes so braces inside text
        # fields do not prematurely terminate the JSON object.
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None

# Role dans le projet:
# Ce fichier valide les sorties JSON du LLM. Il protege les schemas en isolant la logique de recuperation/parsing tolerant.
