def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    step = max(1, chunk_size - overlap)
    return [text[i:i + chunk_size].strip() for i in range(0, len(text), step) if text[i:i + chunk_size].strip()]


def build_section_chunks(document_id: str, sections: dict[str, str]) -> list[dict]:
    chunks = []
    for section, text in sections.items():
        for index, chunk_text in enumerate(split_text(text), start=1):
            chunks.append({"text": chunk_text, "metadata": {"document_id": document_id, "section": section, "chunk_index": index}})
    return chunks

