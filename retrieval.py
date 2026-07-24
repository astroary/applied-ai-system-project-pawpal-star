"""RAG retrieval layer — grounds the AI planner in a pet-care knowledge base.

This module reads the markdown files in ``knowledge_base/``, splits them into
citable chunks (one per ``##`` section), and ranks them against a query using a
dependency-free TF-IDF + cosine-similarity retriever.

The retriever is deliberately pure-Python (no numpy/sklearn) so the system runs
reproducibly anywhere, and every returned chunk carries its source file and
section heading so the planner can cite exactly where a fact came from.

Classes:
    Chunk        — one citable section of the knowledge base.
    Retriever    — loads the knowledge base and ranks chunks against a query.

Run ``python retrieval.py "how long should I walk my puppy"`` for a quick demo.
"""

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Very small English stop-word list — dropped before scoring so that common
# words ("the", "and", "of") don't dominate the similarity calculation.
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "its", "my", "of", "on",
    "or", "should", "than", "that", "the", "their", "them", "then", "there",
    "they", "this", "to", "was", "what", "when", "which", "who", "why",
    "will", "with", "you", "your",
}

# Where the knowledge base lives, relative to this file.
DEFAULT_KB_DIR = Path(__file__).parent / "knowledge_base"


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-letters, and drop stop words and 1-char tokens."""
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


@dataclass
class Chunk:
    """One citable section of the knowledge base.

    Attributes:
        source:  the markdown file the section came from (e.g. "dog_care.md").
        section: the ``##`` heading text (e.g. "Puppy exercise limits").
        text:    the section body used for both scoring and grounding.
        score:   similarity to the most recent query (0.0 until searched).
    """

    source: str
    section: str
    text: str
    score: float = 0.0
    # Cached term frequencies for this chunk, filled in when the KB is indexed.
    _tf: Counter = field(default_factory=Counter, repr=False)

    def citation(self) -> str:
        """Return a short human-readable citation, e.g. "dog_care.md > Feeding"."""
        return f"{self.source} > {self.section}"


class Retriever:
    """Loads the knowledge base and ranks its chunks against a query.

    Usage:
        retriever = Retriever().load()
        hits = retriever.search("how often to feed a puppy", k=3)
    """

    def __init__(self, kb_dir: "str | Path" = DEFAULT_KB_DIR):
        self.kb_dir = Path(kb_dir)
        self.chunks: list[Chunk] = []
        self._idf: dict[str, float] = {}

    # --- Loading & indexing ----------------------------------------------
    def load(self) -> "Retriever":
        """Read every ``*.md`` file, split into chunks, and build the index.

        Returns ``self`` so calls can be chained: ``Retriever().load()``.
        Raises FileNotFoundError if the knowledge-base directory is missing.
        """
        if not self.kb_dir.is_dir():
            raise FileNotFoundError(f"Knowledge base directory not found: {self.kb_dir}")

        self.chunks = []
        for path in sorted(self.kb_dir.glob("*.md")):
            self.chunks.extend(self._split_file(path))

        if not self.chunks:
            raise ValueError(f"No knowledge found in {self.kb_dir} (no *.md sections).")

        self._build_index()
        return self

    @staticmethod
    def _split_file(path: Path) -> list[Chunk]:
        """Split one markdown file into a Chunk per ``##`` section heading.

        Text before the first ``##`` (the intro under the ``#`` title) is kept
        as an "Overview" chunk so no content is silently dropped.
        """
        text = path.read_text(encoding="utf-8")
        chunks: list[Chunk] = []
        current_section = "Overview"
        current_lines: list[str] = []

        def flush() -> None:
            body = "\n".join(current_lines).strip()
            if body:
                chunks.append(Chunk(source=path.name, section=current_section, text=body))

        for line in text.splitlines():
            if line.startswith("## "):
                flush()
                current_section = line[3:].strip()
                current_lines = []
            elif line.startswith("# "):
                continue  # document title — not a retrievable section
            else:
                current_lines.append(line)
        flush()
        return chunks

    def _build_index(self) -> None:
        """Compute each chunk's term frequencies and the corpus-wide IDF."""
        doc_freq: Counter = Counter()
        for chunk in self.chunks:
            chunk._tf = Counter(tokenize(chunk.text))
            for term in chunk._tf:
                doc_freq[term] += 1

        n_docs = len(self.chunks)
        # Smoothed IDF: log(N / (1 + df)) + 1, kept non-negative.
        self._idf = {
            term: math.log(n_docs / (1 + df)) + 1.0
            for term, df in doc_freq.items()
        }

    # --- Scoring ----------------------------------------------------------
    def _vector(self, tf: Counter) -> dict[str, float]:
        """Turn term frequencies into a sparse TF-IDF vector."""
        return {term: freq * self._idf.get(term, 0.0) for term, freq in tf.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        """Cosine similarity between two sparse vectors (0.0 if either is empty)."""
        if not a or not b:
            return 0.0
        # Iterate over the smaller vector for the dot product.
        small, large = (a, b) if len(a) <= len(b) else (b, a)
        dot = sum(weight * large.get(term, 0.0) for term, weight in small.items())
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        """Return the top-``k`` chunks most similar to ``query``, best first.

        Each returned chunk's ``score`` is set to its cosine similarity. Chunks
        with zero similarity are excluded, so an off-topic query can return
        fewer than ``k`` results (or none).
        """
        if not self.chunks:
            raise RuntimeError("Retriever has no data — call load() first.")

        query_vec = self._vector(Counter(tokenize(query)))
        if not query_vec:
            return []

        scored: list[Chunk] = []
        for chunk in self.chunks:
            chunk.score = self._cosine(query_vec, self._vector(chunk._tf))
            if chunk.score > 0.0:
                scored.append(chunk)

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:k]

    # --- Prompt formatting ------------------------------------------------
    @staticmethod
    def format_context(chunks: list[Chunk]) -> str:
        """Format retrieved chunks as numbered, citable sources for a prompt.

        Produces blocks like ``[S1] (dog_care.md > Feeding frequency)\\n...`` so
        the AI planner can ground claims and cite them as [S1], [S2], etc.
        """
        if not chunks:
            return "(no relevant sources found)"
        blocks = []
        for i, chunk in enumerate(chunks, start=1):
            blocks.append(f"[S{i}] ({chunk.citation()})\n{chunk.text}")
        return "\n\n".join(blocks)


def _demo(query: str) -> None:
    """Print the top hits for a query — used when run as a script."""
    retriever = Retriever().load()
    print(f"Indexed {len(retriever.chunks)} chunks from {retriever.kb_dir.name}/\n")
    hits = retriever.search(query, k=3)
    if not hits:
        print(f"No relevant knowledge found for: {query!r}")
        return
    print(f"Top matches for {query!r}:\n")
    for chunk in hits:
        print(f"  [{chunk.score:.3f}] {chunk.citation()}")
        first_line = chunk.text.strip().splitlines()[0]
        print(f"          {first_line}\n")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "how long should I walk my puppy"
    _demo(query)
