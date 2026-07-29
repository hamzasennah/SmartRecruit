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


# Role dans le projet:
# Ce fichier definit le texte de document parse. Il relie upload/parsing aux extracteurs et au chunking RAG.
