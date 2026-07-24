"""Tests for the RAG retrieval layer.

Covers knowledge-base loading/chunking, ranking relevance, citation formatting,
and edge cases (off-topic queries, empty queries, missing directory).
"""

import pytest

from retrieval import Chunk, Retriever, tokenize


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    """A retriever loaded from the real knowledge_base/ directory."""
    return Retriever().load()


# --- Tokenization ---------------------------------------------------------
def test_tokenize_lowercases_and_drops_stopwords():
    """Stop words and punctuation are removed; content words are lowercased."""
    tokens = tokenize("How should I feed my Puppy?")
    assert "puppy" in tokens
    assert "feed" in tokens
    assert "how" not in tokens  # stop word
    assert "i" not in tokens    # single char / stop word


# --- Loading & chunking ---------------------------------------------------
def test_load_indexes_multiple_chunks(retriever):
    """Loading the KB produces many chunks drawn from several source files."""
    assert len(retriever.chunks) >= 10
    sources = {c.source for c in retriever.chunks}
    assert "dog_care.md" in sources
    assert "health_and_safety.md" in sources


def test_chunks_carry_source_and_section(retriever):
    """Every chunk records where it came from, for citation."""
    for chunk in retriever.chunks:
        assert chunk.source.endswith(".md")
        assert chunk.section  # non-empty heading
        assert "> " in chunk.citation()


def test_document_title_is_not_a_chunk(retriever):
    """The top-level ``#`` title line should not become its own section."""
    sections = {c.section for c in retriever.chunks}
    assert "Dog Care Basics" not in sections


# --- Ranking relevance ----------------------------------------------------
def test_search_ranks_relevant_chunk_first(retriever):
    """A puppy-exercise query should surface the puppy-exercise section on top."""
    hits = retriever.search("how much exercise for a young puppy", k=3)
    assert hits, "expected at least one hit"
    top = hits[0]
    assert top.source == "dog_care.md"
    assert "puppy" in top.section.lower()
    assert top.score > 0.0


def test_search_respects_k(retriever):
    """search(k=2) returns at most two chunks, sorted by descending score."""
    hits = retriever.search("feeding schedule for cats and dogs", k=2)
    assert len(hits) <= 2
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_topical_section_outranks_overview(retriever):
    """RAG enhancement: down-weighted 'Overview' intros lose to real sections."""
    hits = retriever.search("feeding schedule frequency for my dog", k=3)
    assert hits[0].section != "Overview"
    assert hits[0].source == "dog_care.md"


def test_heading_terms_boost_matching_section(retriever):
    """RAG enhancement: a query matching a heading retrieves that section first."""
    hits = retriever.search("litter box", k=1)
    assert hits and hits[0].section == "Litter box care"


def test_medication_query_retrieves_safety_section(retriever):
    """A dosing query should retrieve the health/safety boundary chunk.

    This grounds the Phase 3 guardrail: dosing must defer to a veterinarian.
    """
    hits = retriever.search("what medication dose should I give my dog", k=3)
    assert any(h.source == "health_and_safety.md" for h in hits)


# --- Edge cases -----------------------------------------------------------
def test_offtopic_query_returns_no_hits(retriever):
    """A query with no shared vocabulary returns nothing, not a bad match."""
    assert retriever.search("quarterly tax spreadsheet formulas", k=3) == []


def test_empty_query_returns_no_hits(retriever):
    """An empty / stop-word-only query returns nothing rather than erroring."""
    assert retriever.search("", k=3) == []
    assert retriever.search("the and of", k=3) == []


def test_missing_directory_raises():
    """Pointing at a non-existent KB directory fails loudly on load()."""
    with pytest.raises(FileNotFoundError):
        Retriever(kb_dir="knowledge_base_does_not_exist").load()


# --- Prompt formatting ----------------------------------------------------
def test_format_context_numbers_and_cites_sources(retriever):
    """Formatted context is numbered [S1], [S2]... and includes citations."""
    hits = retriever.search("daily walk routine for a dog", k=2)
    context = Retriever.format_context(hits)
    assert "[S1]" in context
    assert " > " in context  # citation marker
    assert hits[0].text.splitlines()[0] in context


def test_format_context_handles_no_hits():
    """Formatting an empty hit list yields a safe placeholder, not a crash."""
    assert Retriever.format_context([]) == "(no relevant sources found)"
