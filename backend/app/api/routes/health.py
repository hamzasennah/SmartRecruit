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
        "nvidia_api_configured": bool(settings.nvidia_api_key),
        "database_enabled": bool(settings.database_url),
    }

# Role dans le projet:
# Ce fichier expose la route de sante. Il renseigne le frontend et les tests sur l'etat minimal de configuration du backend.
