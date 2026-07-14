from app.config import settings
from app.providers.embeddings.qwen_embedding_provider import get_embedding_provider
from app.providers.llm.qwen_vllm_provider import get_llm_provider
from app.providers.reranker.qwen_reranker_provider import get_reranker_provider
from app.providers.vector_store.qdrant_provider import get_vector_store
from app.services.documents.docling_parser import DoclingParser
from app.services.orchestration.batch_ranking_pipeline import BatchRankingPipeline


def get_document_parser() -> DoclingParser:
    return DoclingParser()


def get_batch_ranking_pipeline() -> BatchRankingPipeline:
    return BatchRankingPipeline(
        parser=get_document_parser(),
        llm_provider=get_llm_provider(settings),
        embedding_provider=get_embedding_provider(settings),
        vector_store=get_vector_store(settings),
        reranker=get_reranker_provider(settings),
    )

