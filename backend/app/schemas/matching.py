from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: str
    text: str
    score: float = 0.0
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class CategoryScore(BaseModel):
    name: str
    score: float
    weight: float
    weighted_score: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    details: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)


class CandidateMatch(BaseModel):
    candidate_name: str
    filename: str
    final_score: float
    category_scores: list[CategoryScore]
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
