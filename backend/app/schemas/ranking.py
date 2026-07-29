from pydantic import BaseModel, Field

from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.schemas.matching import CandidateMatch


class RankedCandidate(BaseModel):
    rank: int
    rank_label: str | None = None
    is_tied: bool = False
    candidate: CandidateMatch
    structured_cv: StructuredCV | None = None


class RankingResponse(BaseModel):
    job: StructuredJobDescription
    total_candidates: int
    ranking: list[RankedCandidate] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AnalysisJobCreated(BaseModel):
    analysis_id: str
    status: str
    status_url: str


class AnalysisJobStatus(BaseModel):
    analysis_id: str
    status: str
    progress: int = 0
    result: RankingResponse | None = None
    error: str | None = None

# Role dans le projet:
# Ce fichier definit les reponses de classement et de jobs async. Les routes et le frontend s'appuient sur ce contrat API.
