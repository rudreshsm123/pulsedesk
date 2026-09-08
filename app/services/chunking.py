def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 50) -> list[str]:
    """Splits KB article body into overlapping word-count chunks (~300 tokens each is the
    usual rule of thumb; we approximate tokens with words rather than pulling in a
    tokenizer dependency for this scale of KB). Overlap keeps a sentence that straddles
    a chunk boundary from losing context in both retrieved neighbors."""
    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_size_words:
        return [text.strip()]

    step = chunk_size_words - overlap_words
    chunks = []
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size_words]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size_words >= len(words):
            break

    return chunks
