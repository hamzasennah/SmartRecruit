from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health, ranking
from app.config import settings
from app.core.config_validation import validate_startup_settings
from app.core.logging_config import configure_logging
from app.core.request_context import request_id_context

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup validation fails fast for missing secrets or invalid runtime
    # choices such as an unsupported vector backend.
    validate_startup_settings(settings)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend SmartRecruit pour extraction structuree, normalisation, "
        "matching explicable, retrieval semantique et classement de CV."
    ),
    lifespan=lifespan,
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


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID")
    # Request IDs are stored in context variables so logs and model-audit events
    # can be correlated across nested service calls.
    request_id = incoming.strip() if incoming else uuid4().hex
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "SmartRecruit backend is running",
        "health": f"{settings.api_prefix}/health",
        "docs": "/docs",
    }


# Role dans le projet:
# Ce fichier cree l'application FastAPI. Il valide la configuration, branche les middlewares et expose les routeurs API.
