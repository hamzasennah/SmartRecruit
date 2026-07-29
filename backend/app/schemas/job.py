from pydantic import BaseModel, Field


class RequiredSkills(BaseModel):
    mandatory: list[str] = Field(default_factory=list)
    preferred: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class ExperienceRequirement(BaseModel):
    minimum_months: int = 0
    preferred_job_titles: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)


class EducationRequirement(BaseModel):
    minimum_level: str | None = None
    accepted_fields: list[str] = Field(default_factory=list)


class LanguageRequirement(BaseModel):
    language: str
    minimum_level: str | None = None


class StructuredJobDescription(BaseModel):
    job_title: str | None = None
    required_skills: RequiredSkills = Field(default_factory=RequiredSkills)
    experience_requirements: ExperienceRequirement = Field(default_factory=ExperienceRequirement)
    education_requirements: EducationRequirement = Field(default_factory=EducationRequirement)
    language_requirements: list[LanguageRequirement] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    raw_text_preview: str = ""
    extraction_confidence: float = 0.0


# Role dans le projet:
# Ce fichier definit la fiche de poste structuree. JobExtractor la produit et tous les matchers y lisent les criteres de recrutement.
