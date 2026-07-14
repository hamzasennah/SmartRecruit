class SemanticRetriever:
    def __init__(self, embedding_provider, vector_store, reranker) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._reranker = reranker

    def retrieve(self, namespace: str, query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
        query_vector = self._embedding_provider.embed([query])[0]
        candidates = self._vector_store.search(namespace, query_vector, max(top_k * 3, top_k), filters)
        return self._reranker.rerank(query, candidates, top_k)

