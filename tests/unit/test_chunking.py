from app.services.chunking import chunk_text


def test_short_text_returns_single_chunk():
    text = "This is a short KB article body."
    chunks = chunk_text(text, chunk_size_words=250, overlap_words=50)

    assert chunks == [text]


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_long_text_splits_into_overlapping_chunks():
    words = [f"word{i}" for i in range(600)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size_words=250, overlap_words=50)

    assert len(chunks) > 1
    # Consecutive chunks share the overlap region.
    first_chunk_words = chunks[0].split()
    second_chunk_words = chunks[1].split()
    assert first_chunk_words[-50:] == second_chunk_words[:50]


def test_all_words_are_covered_by_some_chunk():
    words = [f"word{i}" for i in range(600)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size_words=250, overlap_words=50)

    covered = set()
    for chunk in chunks:
        covered.update(chunk.split())
    assert covered == set(words)
