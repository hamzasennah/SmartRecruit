from app.core.model_audit import model_call_context


class SemanticRetriever:
    def __init__(self, embedding_client, vector_store) -> None:
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    def retrieve(self, namespace: str, query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
        document_id = (filters or {}).get("document_id")
        # Query embeddings are audited with candidate context because retrieval
        # quality directly affects the responsibility evidence shown later.
        with model_call_context(
            stage="candidate_evidence_retrieval",
            document_role="cv",
            document_filename=document_id,
            candidate_filename=document_id,
            top_k=top_k,
        ):
            query_vector = self._embedding_client.embed_query(query)
        return self._vector_store.search(namespace, query_vector, top_k, filters)

# Role dans le projet:
# Ce fichier recherche les preuves semantiques. Il vectorise la requete job et interroge le vector store pour le scoring.
