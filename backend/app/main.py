from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health, ranking
from app.config import settings
from app.core.logging_config import configure_logging


configure_logging()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend SmartRecruit pour extraction structuree, normalisation, "
        "matching explicable, retrieval semantique et classement de CV."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(ranking.router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "SmartRecruit backend is running",
        "health": f"{settings.api_prefix}/health",
        "docs": "/docs",
    }

