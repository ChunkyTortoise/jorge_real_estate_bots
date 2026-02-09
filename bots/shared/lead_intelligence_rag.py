"""
Lead Intelligence RAG for Jorge Real Estate AI Bots.

Hybrid retrieval (TF-IDF semantic + keyword) for lead scoring
with similar past conversations. No external dependencies --
uses stdlib math, re, and collections only.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class LeadEmbedding:
    """A stored lead with its TF-IDF embedding and outcome."""

    contact_id: str
    embedding: list[float]
    outcome: str  # converted / lost / pending
    metadata: dict = field(default_factory=dict)
    text: str = ""


@dataclass
class RAGContext:
    """Context returned from augmented retrieval."""

    similar_leads: list[dict]
    avg_conversion_rate: float
    confidence: float
    retrieval_scores: list[float]


class LeadIntelligenceRAG:
    """
    Hybrid retrieval system combining TF-IDF semantic search and
    regex-based keyword search for lead intelligence.

    All vectors are computed in-process with no external dependencies.
    """

    def __init__(self) -> None:
        self.index: list[LeadEmbedding] = []
        self.vocabulary: dict[str, int] = {}
        self._idf_cache: dict[str, float] = {}
        self._dirty = True  # Tracks whether IDF needs recomputation

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase tokenization, stripping non-alphanumeric chars."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def _rebuild_idf(self) -> None:
        """Recompute inverse document frequency from the current index."""
        doc_count = len(self.index)
        if doc_count == 0:
            self._idf_cache = {}
            self.vocabulary = {}
            self._dirty = False
            return

        df: Counter[str] = Counter()
        all_terms: set[str] = set()
        for entry in self.index:
            tokens = set(self._tokenize(entry.text))
            all_terms.update(tokens)
            for token in tokens:
                df[token] += 1

        # Rebuild vocabulary mapping
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(all_terms))}

        # IDF with smoothing: log((N + 1) / (df + 1)) + 1
        self._idf_cache = {}
        for term in all_terms:
            self._idf_cache[term] = math.log((doc_count + 1) / (df[term] + 1)) + 1

        self._dirty = False

    def _compute_tfidf(self, text: str) -> list[float]:
        """Compute a TF-IDF vector for the given text."""
        if self._dirty:
            self._rebuild_idf()

        tokens = self._tokenize(text)
        if not tokens or not self.vocabulary:
            return [0.0] * max(len(self.vocabulary), 1)

        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1

        vec = [0.0] * len(self.vocabulary)
        for term, count in tf.items():
            if term in self.vocabulary:
                idx = self.vocabulary[term]
                normalized_tf = 0.5 + 0.5 * (count / max_tf)
                idf = self._idf_cache.get(term, 1.0)
                vec[idx] = normalized_tf * idf
        return vec

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two equal-length vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_lead(
        self,
        contact_id: str,
        conversation_text: str,
        outcome: str,
        metadata: dict | None = None,
    ) -> None:
        """Compute embedding and store a lead in the index."""
        self._dirty = True  # Vocabulary may have changed
        # We'll compute the embedding lazily on next search; store text now.
        entry = LeadEmbedding(
            contact_id=contact_id,
            embedding=[],  # placeholder, recomputed on search
            outcome=outcome,
            metadata=metadata or {},
            text=conversation_text,
        )
        self.index.append(entry)

    def _ensure_embeddings(self) -> None:
        """Recompute all embeddings if vocabulary changed."""
        if self._dirty:
            self._rebuild_idf()
        for entry in self.index:
            if not entry.embedding or len(entry.embedding) != len(self.vocabulary):
                entry.embedding = self._compute_tfidf(entry.text)

    def search_similar(self, query: str, top_k: int = 5) -> list[tuple[LeadEmbedding, float]]:
        """Return the top-k most semantically similar leads by TF-IDF cosine."""
        if not self.index:
            return []

        self._ensure_embeddings()
        query_vec = self._compute_tfidf(query)

        scored: list[tuple[LeadEmbedding, float]] = []
        for entry in self.index:
            sim = self._cosine_similarity(query_vec, entry.embedding)
            scored.append((entry, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_keyword(self, query: str, top_k: int = 5) -> list[tuple[LeadEmbedding, float]]:
        """
        Regex-based keyword search with relevance scoring.

        Score is the fraction of query tokens found in the document text.
        """
        if not self.index:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[LeadEmbedding, float]] = []
        for entry in self.index:
            doc_lower = entry.text.lower()
            hits = sum(1 for token in query_tokens if re.search(r"\b" + re.escape(token) + r"\b", doc_lower))
            score = hits / len(query_tokens)
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
    ) -> list[tuple[LeadEmbedding, float]]:
        """
        Combine semantic (TF-IDF) and keyword search with weighted scoring.

        Final score = semantic_weight * semantic_score + (1 - semantic_weight) * keyword_score.
        """
        if not self.index:
            return []

        semantic_results = {
            entry.contact_id: score for entry, score in self.search_similar(query, top_k=len(self.index))
        }
        keyword_results = {
            entry.contact_id: score for entry, score in self.search_keyword(query, top_k=len(self.index))
        }

        entry_map = {entry.contact_id: entry for entry in self.index}
        all_ids = set(semantic_results.keys()) | set(keyword_results.keys())

        combined: list[tuple[LeadEmbedding, float]] = []
        kw_weight = 1.0 - semantic_weight
        for cid in all_ids:
            sem_score = semantic_results.get(cid, 0.0)
            kw_score = keyword_results.get(cid, 0.0)
            final = semantic_weight * sem_score + kw_weight * kw_score
            combined.append((entry_map[cid], final))

        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:top_k]

    def augment_context(self, query: str, top_k: int = 3) -> RAGContext:
        """
        Get similar leads and build an augmented context for scoring.

        Returns RAGContext with similar leads, average conversion rate,
        confidence, and retrieval scores.
        """
        results = self.hybrid_search(query, top_k=top_k)

        similar_leads: list[dict] = []
        converted_count = 0
        scores: list[float] = []

        for entry, score in results:
            similar_leads.append(
                {
                    "contact_id": entry.contact_id,
                    "outcome": entry.outcome,
                    "score": round(score, 4),
                    "metadata": entry.metadata,
                }
            )
            scores.append(score)
            if entry.outcome == "converted":
                converted_count += 1

        total = len(similar_leads)
        avg_conversion = converted_count / total if total > 0 else 0.0
        confidence = sum(scores) / total if total > 0 else 0.0

        return RAGContext(
            similar_leads=similar_leads,
            avg_conversion_rate=round(avg_conversion, 4),
            confidence=round(confidence, 4),
            retrieval_scores=scores,
        )
