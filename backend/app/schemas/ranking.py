from pydantic import BaseModel, Field

from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.schemas.matching import CandidateMatch


class RankedCandidate(BaseModel):
    rank: int
    candidate: CandidateMatch
    structured_cv: StructuredCV | None = None


class RankingResponse(BaseModel):
    job: StructuredJobDescription
    total_candidates: int
    ranking: list[RankedCandidate] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

