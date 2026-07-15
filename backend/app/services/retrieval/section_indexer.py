from app.services.retrieval.chunk_builder import build_section_chunks


class SectionIndexer:
    def __init__(self, embedding_client, vector_store) -> None:
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    def index_sections(self, namespace: str, document_id: str, sections: dict[str, str]) -> list[dict]:
        chunks = build_section_chunks(document_id, sections)
        vectors = self._embedding_client.embed([chunk["text"] for chunk in chunks])
        self._vector_store.upsert(namespace, chunks, vectors)
        return chunks
