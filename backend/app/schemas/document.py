from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentKind(StrEnum):
    cv = "cv"
    job = "job"
    unknown = "unknown"


class DocumentText(BaseModel):
    filename: str
    kind: DocumentKind = DocumentKind.unknown
    text: str
    char_count: int = 0
    sections: dict[str, str] = Field(default_factory=dict)

