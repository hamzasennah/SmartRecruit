from pydantic import BaseModel, Field

from app.schemas.experience import ExperienceDuration


class SkillSet(BaseModel):
    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    job_title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    declared_duration: str | None = None
    duration_months: int | None = None
    duration: ExperienceDuration | None = None
    missions: list[str] = Field(default_factory=list)
    skills_used: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    confidence: float = 0.7


class Education(BaseModel):
    degree: str | None = None
    normalized_level: str | None = None
    field: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    confidence: float = 0.7


class Language(BaseModel):
    language: str
    normalized_level: str | None = None
    confidence: float = 1.0
    estimated: bool = False


class Project(BaseModel):
    name: str | None = None
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)


class StructuredCV(BaseModel):
    candidate_name: str | None = None
    job_titles: list[str] = Field(default_factory=list)
    skills: SkillSet = Field(default_factory=SkillSet)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    raw_text_preview: str = ""
    extraction_confidence: float = 0.0

