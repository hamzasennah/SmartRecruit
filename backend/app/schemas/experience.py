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


# Role dans le projet:
# Ce fichier definit les objets de duree et periode d'experience. Les calculs de duree et matchers l'utilisent pour compter les mois fiables.
