from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.render_result_report import render_report
from app.schemas.document import DocumentKind
from app.services.documents.docling_parser import DoclingParser


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse une fiche de poste et un nombre libre de CV PDF.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8002/api/ranking/analyze")
    parser.add_argument("--job-file", default="samples/fiche_poste.pdf")
    parser.add_argument(
        "--cv-file",
        action="append",
        default=None,
        help="Chemin d'un CV PDF. Repete cette option pour analyser plusieurs CV.",
    )
    parser.add_argument(
        "--cv-dir",
        action="append",
        default=None,
        help="Dossier contenant des CV PDF. Tous les PDF du dossier seront analyses.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json-output", default="result.json")
    parser.add_argument("--html-output", default="result_report.html")
    args = parser.parse_args()

    job_path = _existing_path(args.job_file)
    cv_paths = _resolve_cv_paths(args.cv_file, args.cv_dir, job_path)
    result_path = BACKEND_ROOT / args.json_output
    report_path = BACKEND_ROOT / args.html_output
    extracted_texts = _extract_input_texts(job_path, cv_paths)

    print("Analyse en cours...")
    print(f"Fiche de poste: {job_path}")
    print("CV:")
    for path in cv_paths:
        print(f"  - {path}")

    try:
        with httpx.Client(timeout=None) as client:
            with job_path.open("rb") as job_file:
                files = [("job_file", (job_path.name, job_file, "application/pdf"))]
                opened_cvs = []
                try:
                    for cv_path in cv_paths:
                        handle = cv_path.open("rb")
                        opened_cvs.append(handle)
                        files.append(("cv_files", (cv_path.name, handle, "application/pdf")))
                    response = client.post(args.api_url, files=files, data={"top_k": str(args.top_k)})
                finally:
                    for handle in opened_cvs:
                        handle.close()
    except httpx.ConnectError as exc:
        raise SystemExit(
            "Impossible de joindre FastAPI sur http://127.0.0.1:8002.\n"
            "Lance d'abord le backend dans un autre terminal:\n"
            "  cd C:\\Users\\pc\\SmartRecruit\\backend\n"
            "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8002"
        ) from exc

    result_path.write_bytes(response.content)
    if response.status_code >= 400:
        print(f"Erreur API HTTP {response.status_code}. Rapport d'erreur genere.")
    else:
        print("Analyse terminee.")

    render_report(result_path, report_path, extracted_texts=extracted_texts)
    print(f"JSON: {result_path}")
    print(f"Rapport HTML: {report_path}")
    webbrowser.open(report_path.resolve().as_uri())


def _existing_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    return path


def _resolve_cv_paths(cv_files: list[str] | None, cv_dirs: list[str] | None, job_path: Path) -> list[Path]:
    paths: list[Path] = []
    for value in cv_files or []:
        paths.append(_existing_path(value))
    for value in cv_dirs or []:
        directory = _existing_path(value)
        if not directory.is_dir():
            raise NotADirectoryError(f"Dossier CV invalide: {directory}")
        paths.extend(sorted(directory.glob("*.pdf")))
    if not paths:
        paths = [_existing_path("samples/cv1.pdf"), _existing_path("samples/cv2.pdf")]
    job_resolved = job_path.resolve()
    seen: set[Path] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved == job_resolved:
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(resolved)
    if not unique_paths:
        raise FileNotFoundError("Aucun CV PDF trouve. Ajoute au moins un CV different de la fiche de poste.")
    return unique_paths


def _extract_input_texts(job_path: Path, cv_paths: list[Path]) -> list[dict]:
    parser = DoclingParser()
    documents = [
        ("Fiche de poste", parser.extract(job_path, kind=DocumentKind.job)),
    ]
    for index, cv_path in enumerate(cv_paths, start=1):
        documents.append((f"CV {index}", parser.extract(cv_path, kind=DocumentKind.cv)))
    return [
        {
            "label": label,
            "filename": document.filename,
            "char_count": document.char_count,
            "text": document.text,
            "sections": document.sections,
        }
        for label, document in documents
    ]


if __name__ == "__main__":
    main()
