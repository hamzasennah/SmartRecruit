from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.infrastructure.nvidia_embeddings import get_embedding_client  # noqa: E402
from app.infrastructure.nvidia_llm import get_llm_client  # noqa: E402
from app.schemas.ranking import RankingResponse  # noqa: E402
from app.services.documents.docling_parser import DoclingParser  # noqa: E402
from app.services.extraction.cv_extractor import enrich_cv_with_job_skill_evidence  # noqa: E402
from app.services.orchestration.analyze_cv_pipeline import AnalyzeCVPipeline  # noqa: E402
from app.services.orchestration.analyze_job_pipeline import AnalyzeJobPipeline  # noqa: E402
from app.services.ranking.ranking_engine import RankingEngine  # noqa: E402
from app.services.retrieval.section_indexer import SectionIndexer  # noqa: E402
from app.services.retrieval.semantic_retriever import SemanticRetriever  # noqa: E402
from app.services.scoring.scoring_engine import ScoringEngine  # noqa: E402


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def reset_namespace(self, namespace: str) -> None:
        self.rows = [row for row in self.rows if row["namespace"] != namespace]

    def upsert(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
        for chunk, vector in zip(chunks, vectors, strict=True):
            metadata = chunk.get("metadata", {}) or {}
            self.rows.append(
                {
                    "id": str(uuid4()),
                    "namespace": namespace,
                    "text": chunk["text"],
                    "vector": vector,
                    "metadata": {
                        "document_id": str(metadata.get("document_id", "")),
                        "section": str(metadata.get("section", "")),
                        "chunk_index": int(metadata.get("chunk_index", 0)),
                    },
                }
            )

    def search(self, namespace: str, query_vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        rows = [row for row in self.rows if row["namespace"] == namespace]
        if "document_id" in filters:
            rows = [row for row in rows if row["metadata"]["document_id"] == str(filters["document_id"])]
        if "section" in filters:
            rows = [row for row in rows if row["metadata"]["section"] == str(filters["section"])]
        scored = [
            {
                "id": row["id"],
                "text": row["text"],
                "metadata": row["metadata"],
                "score": _cosine(query_vector, row["vector"]),
            }
            for row in rows
        ]
        return sorted(scored, key=lambda item: (-item["score"], item["metadata"]["document_id"], item["metadata"]["chunk_index"]))[:top_k]

    def create_job_record(self, *args, **kwargs) -> str:
        return "diagnostic-job"

    def create_resume_record(self, *args, **kwargs) -> str:
        return "diagnostic-resume"

    def create_analysis_record(self, *args, **kwargs) -> str:
        return "diagnostic-analysis"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostique la reproductibilite des scores sans afficher le texte des CV.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--job-file", default="")
    parser.add_argument("--cv-file", action="append", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json-output", default="")
    parser.add_argument("--offline", action="store_true", help="Utilise des clients LLM/embeddings deterministes sans appel NVIDIA.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="smartrecruit_repro_") as tmp:
        job_path, cv_paths = _resolve_inputs(args, Path(tmp))
        results = [_run_once(index + 1, job_path, cv_paths, args.top_k, offline=args.offline) for index in range(args.runs)]

    report = {
        "runs": results,
        "all_final_hashes_identical": len({run["final_hash"] for run in results}) == 1,
        "all_scores_identical": len({_stable_json(run["scores"]) for run in results}) == 1,
        "llm_parameters": {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "seed": settings.llm_seed,
            "max_tokens": settings.llm_max_tokens,
            "offline": args.offline,
        },
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_output:
        Path(args.json_output).write_text(output, encoding="utf-8")
    print(output)
    return 0 if report["all_scores_identical"] else 1


def _resolve_inputs(args: argparse.Namespace, tmp_dir: Path) -> tuple[Path, list[Path]]:
    if args.job_file and args.cv_file:
        return Path(args.job_file), [Path(value) for value in args.cv_file]
    job_path = tmp_dir / "job.txt"
    good_cv = tmp_dir / "cv_data_analyst.txt"
    weak_cv = tmp_dir / "cv_generalist.txt"
    job_path.write_text(
        "Data Analyst. Python, SQL, Power BI. 2 ans experience. Construire des dashboards KPI.",
        encoding="utf-8",
    )
    good_cv.write_text(
        "Hamza Data Analyst. Experience janvier 2022 a decembre 2024. Python SQL PowerBI dashboards KPI.",
        encoding="utf-8",
    )
    weak_cv.write_text(
        "Profil generaliste communication et support commercial. Coordination equipe et reporting simple.",
        encoding="utf-8",
    )
    return job_path, [good_cv, weak_cv]


def _run_once(run_index: int, job_path: Path, cv_paths: list[Path], top_k: int, offline: bool = False) -> dict:
    parser = DoclingParser()
    llm_client = StaticLLMClient() if offline else get_llm_client(settings)
    embedding_client = StableEmbeddingClient() if offline else get_embedding_client(settings)
    vector_store = InMemoryVectorStore()
    job_pipeline = AnalyzeJobPipeline(parser, llm_client)
    cv_pipeline = AnalyzeCVPipeline(parser, llm_client)
    indexer = SectionIndexer(embedding_client, vector_store)
    retriever = SemanticRetriever(embedding_client, vector_store)
    scoring = ScoringEngine()
    ranking = RankingEngine()
    namespace = f"diagnostic_{run_index}_{uuid4().hex}"

    job = job_pipeline.run(job_path)
    query = " ".join(
        [
            job.job_title or "",
            " ".join(job.required_skills.mandatory),
            " ".join(job.required_skills.preferred),
            " ".join(job.responsibilities),
        ]
    )
    stage_hashes: dict[str, object] = {"job_structured": _hash_model(job)}
    matches = []
    cv_stage_hashes = []
    for cv_path in cv_paths:
        document, cv = cv_pipeline.run(cv_path)
        enrich_cv_with_job_skill_evidence(cv, document.text, job)
        chunks = indexer.index_sections(namespace, document.filename, document.sections)
        evidence = retriever.retrieve(namespace, query, top_k=top_k, filters={"document_id": document.filename})
        match = scoring.score_candidate(document.filename, cv, job, evidence)
        matches.append((match, cv))
        cv_stage_hashes.append(
            {
                "filename": document.filename,
                "text_hash": _hash_text(document.text),
                "sections_hash": _hash_json(document.sections),
                "structured_cv_hash": _hash_model(cv),
                "chunks_hash": _hash_json([_without_text(chunk) for chunk in chunks]),
                "evidence_hash": _hash_json([_without_text(row) for row in evidence]),
                "score": match.final_score,
            }
        )
    response = RankingResponse(job=job, total_candidates=len(matches), ranking=ranking.rank(matches), errors=[])
    return {
        "run": run_index,
        "stage_hashes": {**stage_hashes, "candidates": cv_stage_hashes},
        "scores": [
            {
                "rank": row.rank,
                "filename": row.candidate.filename,
                "candidate_name": row.candidate.candidate_name,
                "final_score": row.candidate.final_score,
            }
            for row in response.ranking
        ],
        "final_hash": _hash_model(response),
    }


def _without_text(value: dict) -> dict:
    cleaned = dict(value)
    cleaned.pop("id", None)
    cleaned.pop("text", None)
    return cleaned


class StaticLLMClient:
    def generate_json(self, prompt: str) -> dict:
        if "FICHE DE POSTE:" in prompt:
            return {
                "job_title": "Data Analyst",
                "required_skills": {"mandatory": ["Python", "SQL", "Power BI"], "preferred": ["dashboard"], "soft": []},
                "experience_requirements": {"minimum_months": 24, "preferred_job_titles": ["Data Analyst"], "required_domains": []},
                "education_requirements": {"minimum_level": None, "accepted_fields": []},
                "language_requirements": [],
                "certifications": [],
                "responsibilities": ["Construire des dashboards KPI"],
            }
        if "generaliste" in prompt.lower():
            return {
                "candidate_name": "Profil Generaliste",
                "job_titles": ["Support commercial"],
                "skills": {"technical": [], "soft": ["communication"], "tools": []},
                "experiences": [],
                "education": [],
                "languages": [],
                "certifications": [],
                "projects": [],
            }
        return {
            "candidate_name": "Hamza Data Analyst",
            "job_titles": ["Data Analyst"],
            "skills": {"technical": ["Python", "SQL"], "soft": [], "tools": ["Power BI"]},
            "experiences": [
                {
                    "job_title": "Data Analyst",
                    "company": None,
                    "start_date": "janvier 2022",
                    "end_date": "decembre 2024",
                    "missions": ["Python SQL PowerBI dashboards KPI"],
                    "skills_used": ["Python", "SQL", "Power BI"],
                }
            ],
            "education": [],
            "languages": [],
            "certifications": [],
            "projects": [],
        }


class StableEmbeddingClient:
    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [_embedding_for_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return _embedding_for_text(text)


def _embedding_for_text(text: str) -> list[float]:
    digest = sha256(text.encode("utf-8")).digest()
    return [((digest[index] / 255.0) * 2) - 1 for index in range(16)]


def _hash_model(value) -> str:
    return _hash_json(value.model_dump(mode="json"))


def _hash_json(value) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _stable_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
