from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import ExternalServiceError
from app.core.model_audit import model_call_context
from app.schemas.ranking import RankingResponse
from app.services.extraction.cv_extractor import enrich_cv_with_job_skill_evidence
from app.services.orchestration.analyze_cv_pipeline import AnalyzeCVPipeline
from app.services.orchestration.analyze_job_pipeline import AnalyzeJobPipeline
from app.services.ranking.ranking_engine import RankingEngine
from app.services.retrieval.section_indexer import SectionIndexer
from app.services.retrieval.semantic_retriever import SemanticRetriever
from app.services.scoring.scoring_engine import ScoringEngine


class BatchRankingPipeline:
    def __init__(self, parser, llm_client, embedding_client, vector_store) -> None:
        self._job_pipeline = AnalyzeJobPipeline(parser, llm_client)
        self._cv_pipeline = AnalyzeCVPipeline(parser, llm_client)
        self._indexer = SectionIndexer(embedding_client, vector_store)
        self._retriever = SemanticRetriever(embedding_client, vector_store)
        self._vector_store = vector_store
        self._scoring = ScoringEngine()
        self._ranking = RankingEngine()

    def run(self, job_path, cv_paths, top_k: int = 5) -> RankingResponse:
        namespace = f"analysis_{uuid4().hex}"
        self._vector_store.reset_namespace(namespace)
        try:
            job_file_path, job_filename = _path_and_filename(job_path)
            with model_call_context(analysis_namespace=namespace, document_role="job", document_filename=job_filename):
                job = self._job_pipeline.run(job_file_path, filename_override=job_filename)
            job_id = _create_job_record(self._vector_store, job_file_path, job_filename, job)
            matches, errors = [], []
            query = " ".join(
                [
                    job.job_title or "",
                    " ".join(job.required_skills.mandatory),
                    " ".join(job.required_skills.preferred),
                    " ".join(job.responsibilities),
                ]
            )
            for cv_ref in cv_paths:
                cv_path, cv_filename = _path_and_filename(cv_ref)
                try:
                    with model_call_context(
                        analysis_namespace=namespace,
                        document_role="cv",
                        document_filename=cv_filename,
                        candidate_filename=cv_filename,
                    ):
                        document, cv = self._cv_pipeline.run(cv_path, filename_override=cv_filename)
                        enrich_cv_with_job_skill_evidence(cv, document.text, job)
                        _create_resume_record(self._vector_store, cv_path, document, cv)
                        self._indexer.index_sections(namespace, document.filename, document.sections)
                        evidence = self._retriever.retrieve(
                            namespace,
                            query,
                            top_k=top_k,
                            filters={"document_id": document.filename},
                        )
                        matches.append((self._scoring.score_candidate(document.filename, cv, job, evidence, document.sections), cv))
                except ExternalServiceError:
                    raise
                except Exception:
                    errors.append(f"{cv_filename}: analyse impossible")
            response = RankingResponse(
                job=job,
                total_candidates=len(matches),
                ranking=self._ranking.rank(matches),
                errors=errors,
            )
            _create_analysis_record(self._vector_store, namespace, job_id, response)
            return response
        finally:
            self._vector_store.reset_namespace(namespace)


def _path_and_filename(value) -> tuple[Path, str]:
    if hasattr(value, "path") and hasattr(value, "original_filename"):
        return Path(value.path), str(value.original_filename)
    path = Path(value)
    return path, path.name


def _create_job_record(vector_store, path, filename: str, job) -> str | None:
    if not hasattr(vector_store, "create_job_record"):
        return None
    return vector_store.create_job_record(
        filename=filename,
        content_hash=_file_hash(path),
        job_title=job.job_title,
        text_preview=job.raw_text_preview,
    )


def _create_resume_record(vector_store, path, document, cv) -> str | None:
    if not hasattr(vector_store, "create_resume_record"):
        return None
    return vector_store.create_resume_record(
        filename=document.filename or Path(path).name,
        content_hash=_file_hash(path),
        candidate_name=cv.candidate_name,
        text_preview=document.text,
    )


def _create_analysis_record(vector_store, namespace: str, job_id: str | None, response: RankingResponse) -> str | None:
    if not hasattr(vector_store, "create_analysis_record"):
        return None
    return vector_store.create_analysis_record(
        namespace=namespace,
        job_id=job_id,
        total_candidates=response.total_candidates,
        summary=_analysis_summary(response),
        result=response.model_dump(mode="json"),
    )


def _file_hash(path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _analysis_summary(response: RankingResponse) -> str:
    if not response.ranking:
        return "Aucun candidat classe."
    best = response.ranking[0].candidate
    return f"{response.total_candidates} candidat(s) analyses. Meilleur score: {best.candidate_name} ({best.final_score:.2f}%)."
