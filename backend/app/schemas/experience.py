from pydantic import BaseModel


class ExperienceDuration(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    duration_years: float | None = None
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

