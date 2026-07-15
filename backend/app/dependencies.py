from app.config import settings
from app.infrastructure.postgres_vector_store import get_vector_store
from app.infrastructure.qwen_embeddings import get_embedding_client
from app.infrastructure.qwen_llm import get_llm_client
from app.services.documents.docling_parser import DoclingParser
from app.services.orchestration.batch_ranking_pipeline import BatchRankingPipeline


def get_document_parser() -> DoclingParser:
    return DoclingParser()


def get_batch_ranking_pipeline() -> BatchRankingPipeline:
    return BatchRankingPipeline(
        parser=get_document_parser(),
        llm_client=get_llm_client(settings),
        embedding_client=get_embedding_client(settings),
        vector_store=get_vector_store(settings),
    )
