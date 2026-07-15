from pathlib import Path
from uuid import uuid4

from app.core.exceptions import ExternalServiceError
from app.schemas.ranking import RankingResponse
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
        job = self._job_pipeline.run(job_path)
        matches, errors = [], []
        query = " ".join([job.job_title or "", " ".join(job.required_skills.mandatory), " ".join(job.required_skills.preferred), " ".join(job.responsibilities)])
        for cv_path in cv_paths:
            try:
                document, cv = self._cv_pipeline.run(cv_path)
                self._indexer.index_sections(namespace, document.filename, document.sections)
                evidence = self._retriever.retrieve(namespace, query, top_k=top_k, filters={"document_id": document.filename})
                matches.append((self._scoring.score_candidate(document.filename, cv, job, evidence), cv))
            except ExternalServiceError:
                raise
            except Exception as exc:
                errors.append(f"{Path(cv_path).name}: {exc}")
        return RankingResponse(job=job, total_candidates=len(matches), ranking=self._ranking.rank(matches), errors=errors)
