from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import settings
from app.core.constants import SUPPORTED_EXTENSIONS


class UploadPolicyError(ValueError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class SavedUpload:
    path: Path
    original_filename: str
    size_bytes: int


def create_analysis_upload_dir(analysis_id: str) -> Path:
    target = settings.upload_dir / f"analysis_{analysis_id}"
    target.mkdir(parents=True, exist_ok=False)
    return target


def cleanup_upload_dir(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


async def save_upload(file: UploadFile, target_dir: Path, role: str) -> SavedUpload:
    original_name = _safe_original_filename(file.filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UploadPolicyError(400, f"Format non supporte: {suffix or 'sans extension'}")

    target = target_dir / f"{role}_{uuid4().hex}{suffix}"
    size = 0
    first_chunk = b""

    try:
        with target.open("wb") as output:
            while True:
                chunk = await file.read(settings.upload_chunk_bytes)
                if not chunk:
                    break
                if not first_chunk:
                    first_chunk = chunk[:256]
                size += len(chunk)
                # Size is checked while streaming so large files are rejected
                # before they are fully written to disk.
                if size > settings.max_upload_bytes:
                    raise UploadPolicyError(413, "Fichier trop volumineux.")
                output.write(chunk)
    except UploadPolicyError:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if size == 0:
        target.unlink(missing_ok=True)
        raise UploadPolicyError(400, "Fichier vide.")
    if not _content_matches_extension(suffix, first_chunk):
        # Lightweight magic-byte checks reduce accidental or spoofed uploads
        # before document parsers see the file.
        target.unlink(missing_ok=True)
        raise UploadPolicyError(400, "Le contenu du fichier ne correspond pas a son extension.")
    return SavedUpload(path=target, original_filename=original_name, size_bytes=size)


def ensure_cv_quota(cv_files: list[UploadFile]) -> None:
    if not cv_files:
        raise UploadPolicyError(400, "Ajoutez au moins un CV.")


def ensure_total_upload_quota(uploads: list[SavedUpload]) -> None:
    total = sum(upload.size_bytes for upload in uploads)
    if total > settings.max_total_upload_bytes:
        raise UploadPolicyError(413, "Taille cumulee des fichiers trop volumineuse.")


def _safe_original_filename(value: str | None) -> str:
    candidate = Path(value or "document").name.strip()
    # Keep the original filename for display/audit, but remove path separators
    # and unusual characters before storing it in metadata.
    candidate = re.sub(r"[^A-Za-z0-9._ -]+", "_", candidate)
    candidate = candidate.strip(" ._-")
    return candidate or "document"


def _content_matches_extension(suffix: str, first_chunk: bytes) -> bool:
    if suffix == ".pdf":
        return first_chunk.startswith(b"%PDF")
    if suffix == ".docx":
        return first_chunk.startswith(b"PK")
    if suffix in {".txt", ".md"}:
        return b"\x00" not in first_chunk
    return False

# Role dans le projet:
# Ce fichier gere sauvegarde temporaire et politiques d'upload. Les routes l'appellent avant tout parsing ou appel modele.
