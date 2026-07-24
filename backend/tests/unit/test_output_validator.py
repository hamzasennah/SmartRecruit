import pytest
from app.core.exceptions import OutputValidationError
from app.services.extraction.output_validator import parse_json_payload


def test_parse_json_payload_accepts_plain_json() -> None:
    assert parse_json_payload('{"candidate_name": "Hamza"}') == {"candidate_name": "Hamza"}


def test_parse_json_payload_extracts_markdown_json_block() -> None:
    raw = '```json\n{"candidate_name": "Hamza", "skills": {"technical": []}}\n```'

    assert parse_json_payload(raw) == {"candidate_name": "Hamza", "skills": {"technical": []}}


def test_parse_json_payload_extracts_balanced_json_from_llm_text() -> None:
    raw = 'Voici le resultat demandé:\n{"job": {"title": "Data Analyst"}, "score": 1}\nFin.'

    assert parse_json_payload(raw) == {"job": {"title": "Data Analyst"}, "score": 1}


def test_parse_json_payload_rejects_invalid_response() -> None:
    with pytest.raises(OutputValidationError):
        parse_json_payload("Je ne peux pas fournir ce JSON.")
