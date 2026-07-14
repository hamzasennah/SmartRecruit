def merge_retrieval_results(*groups: list[dict], limit: int = 8) -> list[dict]:
    rows = [item for group in groups for item in group]
    return sorted(rows, key=lambda item: item.get("rerank_score", item.get("score", 0)), reverse=True)[:limit]
