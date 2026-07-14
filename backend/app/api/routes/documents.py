from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.core.constants import SUPPORTED_EXTENSIONS
from app.core.exceptions import DocumentParsingError
from app.dependencies import get_document_parser
from app.schemas.document import DocumentKind, DocumentText

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/parse", response_model=DocumentText)
async def parse_document(file: UploadFile = File(...), kind: DocumentKind = DocumentKind.unknown) -> DocumentText:
    path = await _save_upload(file)
    try:
        return get_document_parser().extract(path, kind=kind)
    except DocumentParsingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporte: {suffix}")
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / Path(file.filename or f"upload{suffix}").name
    content = await file.read()
    target.write_bytes(content)
    return target

