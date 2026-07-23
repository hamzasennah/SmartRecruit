import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.core.constants import SUPPORTED_EXTENSIONS
from app.core.exceptions import ExternalServiceError, SmartRecruitError
from app.dependencies import get_batch_ranking_pipeline
from app.schemas.ranking import RankingResponse

router = APIRouter(prefix="/ranking", tags=["ranking"])
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=RankingResponse)
async def analyze_ranking(job_file: UploadFile = File(...), cv_files: list[UploadFile] = File(...), top_k: int = Form(default=5, ge=1, le=20)) -> RankingResponse:
    job_path = await _save_upload(job_file, "job_")
    cv_paths = [await _save_upload(file, "cv_") for file in cv_files]
    try:
        return get_batch_ranking_pipeline().run(job_path, cv_paths, top_k=top_k)
    except ExternalServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SmartRecruitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erreur inattendue pendant l'analyse du classement.")
        raise HTTPException(status_code=500, detail=f"Erreur interne pendant l'analyse: {exc}") from exc


async def _save_upload(file: UploadFile, prefix: str) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporte: {suffix}")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{prefix}{Path(file.filename or f'document{suffix}').name}"
    target.write_bytes(await file.read())
    return target
