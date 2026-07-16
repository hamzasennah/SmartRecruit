class SemanticRetriever:
    def __init__(self, embedding_client, vector_store) -> None:
        self._embedding_client = embedding_client
        self._vector_store = vector_store

    def retrieve(self, namespace: str, query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
        query_vector = self._embedding_client.embed_query(query)
        return self._vector_store.search(namespace, query_vector, top_k, filters)
