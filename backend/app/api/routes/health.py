from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "database_enabled": bool(settings.database_url),
    }
