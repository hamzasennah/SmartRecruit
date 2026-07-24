from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.exceptions import DocumentParsingError
from app.core.security import check_rate_limit, require_api_key
from app.dependencies import get_document_parser
from app.schemas.document import DocumentKind, DocumentText
from app.services.documents.upload_manager import UploadPolicyError, cleanup_upload_dir, create_analysis_upload_dir, save_upload

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_api_key), Depends(check_rate_limit)],
)


@router.post("/parse", response_model=DocumentText)
async def parse_document(file: Annotated[UploadFile, File(...)], kind: DocumentKind = DocumentKind.unknown) -> DocumentText:
    upload_dir = create_analysis_upload_dir(uuid4().hex)
    try:
        upload = await save_upload(file, upload_dir, "document")
        return get_document_parser().extract(upload.path, kind=kind, filename_override=upload.original_filename)
    except UploadPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except DocumentParsingError as exc:
        raise HTTPException(status_code=400, detail="Document impossible a analyser.") from exc
    finally:
        cleanup_upload_dir(upload_dir)

