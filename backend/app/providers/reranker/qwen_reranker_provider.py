from app.config import Settings
from app.services.normalization.text_normalizer import tokenize


class QwenRerankerProvider:
    def rerank(self, query: str, documents: list[dict], top_k: int) -> list[dict]:
        query_tokens = set(tokenize(query))
        for document in documents:
            document_tokens = set(tokenize(str(document.get("text", ""))))
            lexical = len(query_tokens.intersection(document_tokens)) / len(query_tokens) if query_tokens else 0.0
            document["rerank_score"] = round(0.7 * float(document.get("score", 0.0)) + 0.3 * lexical, 4)
        return sorted(documents, key=lambda item: item["rerank_score"], reverse=True)[:top_k]


def get_reranker_provider(settings: Settings) -> QwenRerankerProvider:
    return QwenRerankerProvider()

