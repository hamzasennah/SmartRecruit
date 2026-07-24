from app.config import settings
from app.services.retrieval.chunk_builder import build_section_chunks


class SectionIndexer:
    def __init__(self, embedding_client, vector_store) -> None:
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    def index_sections(self, namespace: str, document_id: str, sections: dict[str, str]) -> list[dict]:
        chunks = build_section_chunks(document_id, sections)
        for batch in _batches(chunks, settings.embedding_batch_size):
            vectors = self._embedding_client.embed_passages([chunk["text"] for chunk in batch])
            self._vector_store.upsert(namespace, batch, vectors)
        return chunks


def _batches(items: list[dict], size: int) -> list[list[dict]]:
    size = max(1, size)
    return [items[index : index + size] for index in range(0, len(items), size)]
