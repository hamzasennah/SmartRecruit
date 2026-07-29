from app.config import settings
from app.core.model_audit import model_call_context
from app.services.retrieval.chunk_builder import build_section_chunks


class SectionIndexer:
    def __init__(self, embedding_client, vector_store) -> None:
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    def index_sections(self, namespace: str, document_id: str, sections: dict[str, str]) -> list[dict]:
        chunks = build_section_chunks(document_id, sections)
        for batch in _batches(chunks, settings.embedding_batch_size):
            section_names = ",".join(sorted({str(chunk["metadata"].get("section", "")) for chunk in batch}))
            # The audit context records the section batch around each embedding
            # call so retrieval issues can be traced back to source sections.
            with model_call_context(
                stage="cv_section_indexing",
                document_role="cv",
                document_filename=document_id,
                candidate_filename=document_id,
                section_names=section_names,
                chunk_count=len(batch),
            ):
                vectors = self._embedding_client.embed_passages([chunk["text"] for chunk in batch])
            self._vector_store.upsert(namespace, batch, vectors)
        return chunks


def _batches(items: list[dict], size: int) -> list[list[dict]]:
    # Batching protects the external embedding API from large one-shot payloads.
    size = max(1, size)
    return [items[index : index + size] for index in range(0, len(items), size)]

# Role dans le projet:
# Ce fichier indexe les sections de CV dans le vector store. Il relie chunk_builder, embeddings NVIDIA et persistence vectorielle.
