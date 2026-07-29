import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ExternalServiceError, SmartRecruitError
from app.core.request_context import analysis_id_context
from app.core.security import check_rate_limit, require_api_key
from app.dependencies import get_batch_ranking_pipeline
from app.schemas.ranking import AnalysisJobCreated, AnalysisJobStatus, RankingResponse
from app.services.documents.upload_manager import (
    UploadPolicyError,
    cleanup_upload_dir,
    create_analysis_upload_dir,
    ensure_cv_quota,
    ensure_total_upload_quota,
    save_upload,
)
from app.services.orchestration.job_manager import analysis_job_manager

router = APIRouter(
    prefix="/ranking",
    tags=["ranking"],
    dependencies=[Depends(require_api_key)],
)
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=RankingResponse, dependencies=[Depends(check_rate_limit)])
async def analyze_ranking(
    job_file: Annotated[UploadFile, File(...)],
    cv_files: Annotated[list[UploadFile], File(...)],
    top_k: Annotated[int, Form(ge=1, le=20)] = 5,
) -> RankingResponse:
    analysis_id = uuid4().hex
    token = analysis_id_context.set(analysis_id)
    upload_dir = create_analysis_upload_dir(analysis_id)
    try:
        # Upload validation happens before parsing/model calls so unsafe or
        # oversized input fails cheaply and consistently.
        ensure_cv_quota(cv_files)
        job_upload = await save_upload(job_file, upload_dir, "job")
        cv_uploads = [await save_upload(file, upload_dir, "cv") for file in cv_files]
        ensure_total_upload_quota([job_upload, *cv_uploads])
        logger.info(
            "Analyse demarree.",
            extra={
                "analysis_id": analysis_id,
                "cv_count": len(cv_uploads),
                "total_upload_bytes": sum(item.size_bytes for item in [job_upload, *cv_uploads]),
            },
        )
        result = await run_in_threadpool(
            # The ranking pipeline performs blocking parsing, DB, and provider
            # calls, so it is moved off the event loop.
            get_batch_ranking_pipeline().run,
            job_upload,
            cv_uploads,
            top_k,
        )
        logger.info("Analyse terminee.", extra={"analysis_id": analysis_id, "total_candidates": result.total_candidates})
        return result
    except UploadPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ExternalServiceError as exc:
        logger.warning("Service externe indisponible pendant l'analyse.", exc_info=exc, extra={"analysis_id": analysis_id})
        raise HTTPException(status_code=503, detail="Service externe indisponible pendant l'analyse.") from exc
    except SmartRecruitError as exc:
        logger.info("Analyse refusee par une regle metier.", exc_info=exc, extra={"analysis_id": analysis_id})
        raise HTTPException(status_code=400, detail="Analyse impossible avec les documents fournis.") from exc
    except Exception as exc:
        logger.exception("Erreur inattendue pendant l'analyse du classement.", extra={"analysis_id": analysis_id})
        raise HTTPException(status_code=500, detail="Erreur interne pendant l'analyse.") from exc
    finally:
        cleanup_upload_dir(upload_dir)
        analysis_id_context.reset(token)


@router.post("/jobs", response_model=AnalysisJobCreated, status_code=202, dependencies=[Depends(check_rate_limit)])
async def create_ranking_job(
    job_file: Annotated[UploadFile, File(...)],
    cv_files: Annotated[list[UploadFile], File(...)],
    top_k: Annotated[int, Form(ge=1, le=20)] = 5,
) -> AnalysisJobCreated:
    upload_dir = create_analysis_upload_dir(uuid4().hex)
    try:
        # Async jobs persist uploads until the background worker finishes; the
        # manager owns cleanup after this point.
        ensure_cv_quota(cv_files)
        job_upload = await save_upload(job_file, upload_dir, "job")
        cv_uploads = [await save_upload(file, upload_dir, "cv") for file in cv_files]
        ensure_total_upload_quota([job_upload, *cv_uploads])
        job = analysis_job_manager.submit(
            get_batch_ranking_pipeline,
            job_upload,
            cv_uploads,
            top_k,
            upload_dir,
        )
        return AnalysisJobCreated(
            analysis_id=job.analysis_id,
            status=job.status,
            status_url=f"/api/ranking/jobs/{job.analysis_id}",
        )
    except UploadPolicyError as exc:
        cleanup_upload_dir(upload_dir)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        cleanup_upload_dir(upload_dir)
        logger.exception("Erreur inattendue pendant la creation du job d'analyse.")
        raise HTTPException(status_code=500, detail="Erreur interne pendant la creation de l'analyse.") from exc


@router.get("/jobs/{analysis_id}", response_model=AnalysisJobStatus)
def get_ranking_job(analysis_id: str) -> AnalysisJobStatus:
    status = analysis_job_manager.get_status(analysis_id)
    if not status:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    return status


@router.delete("/jobs/{analysis_id}", response_model=AnalysisJobStatus)
def cancel_ranking_job(analysis_id: str) -> AnalysisJobStatus:
    # Cancellation exposes best-effort control to the UI; a running model call
    # may still finish before the worker sees the cancel flag.
    status = analysis_job_manager.cancel(analysis_id)
    if not status:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    return status

# Role dans le projet:
# Ce fichier expose les endpoints de classement synchrones et asynchrones. Il applique securite, quotas d'upload et delegation au BatchRankingPipeline.
