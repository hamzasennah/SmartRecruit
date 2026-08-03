from pydantic import BaseModel, Field


class ExperienceDuration(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    duration_years: float | None = None
    source_text: str | None = None
    start_precision: str = "unknown"
    end_precision: str = "unknown"
    calculation_source: str = "unknown"
    confidence: float = 0.0
    estimated: bool = False
    error: str | None = None


class ExperiencePeriod(BaseModel):
    start_date: str
    end_date: str
    duration_months: int
    confidence: float = 1.0


class ExperienceDurationTrace(BaseModel):
    job_title: str | None = None
    company: str | None = None
    start_date_raw: str | None = None
    end_date_raw: str | None = None
    declared_duration: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    calculation_source: str = "unknown"
    source_text: str | None = None
    counted_in_total: bool = False
    error: str | None = None


class ExperienceTotals(BaseModel):
    total_months: int = 0
    total_years: float = 0.0
    calculated_total_months: int | None = None
    dated_months: int = 0
    explicit_duration_months: int = 0
    declared_total_months: int | None = None
    period_count: int = 0
    explicit_duration_count: int = 0
    overlap_policy: str = "union"
    calculation_source: str = "none"
    calculation_status: str = "not_available"
    failure_reason: str | None = None
    entries: list[ExperienceDurationTrace] = Field(default_factory=list)


# Role dans le projet:
# Ce fichier definit les objets de duree et periode d'experience. Les calculs de duree et matchers l'utilisent pour compter les mois fiables.
