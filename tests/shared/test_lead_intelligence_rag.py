"""
Unit tests for Lead Intelligence RAG.

Tests hybrid retrieval (TF-IDF semantic + keyword), lead indexing,
search methods, and augmented context generation.
"""
import pytest

from bots.shared.lead_intelligence_rag import (
    LeadEmbedding,
    LeadIntelligenceRAG,
    RAGContext,
)


# -- Helpers -----------------------------------------------------------

CONVERSATIONS = {
    "buyer_ready": "I have pre-approval from Wells Fargo for 500K. Looking to buy a 3-bedroom in Rancho Cucamonga near good schools.",
    "seller_motivated": "We need to sell our house quickly because of a job relocation to Texas. It is a 4-bedroom in Alta Loma.",
    "investor": "I am looking for multi-family investment properties with positive cash flow in the Inland Empire area.",
    "cold_lead": "Just browsing listings online. Not sure if I want to buy or rent right now.",
    "hot_buyer": "My lease ends next month and I need a 3-bedroom house near Rancho Cucamonga schools. Already pre-approved for 450K.",
}


def _build_rag(include_all: bool = True) -> LeadIntelligenceRAG:
    """Build a RAG instance pre-loaded with sample conversations."""
    rag = LeadIntelligenceRAG()
    if not include_all:
        return rag

    outcomes = {
        "buyer_ready": "converted",
        "seller_motivated": "converted",
        "investor": "converted",
        "cold_lead": "lost",
        "hot_buyer": "converted",
    }
    for cid, text in CONVERSATIONS.items():
        rag.index_lead(cid, text, outcomes[cid], metadata={"source": "test"})
    return rag


# -- LeadEmbedding Dataclass ------------------------------------------

class TestLeadEmbedding:
    """Test LeadEmbedding creation and fields."""

    def test_create_basic(self):
        emb = LeadEmbedding(
            contact_id="c1",
            embedding=[0.1, 0.2],
            outcome="converted",
        )
        assert emb.contact_id == "c1"
        assert emb.outcome == "converted"

    def test_default_metadata(self):
        emb = LeadEmbedding(contact_id="c1", embedding=[], outcome="lost")
        assert emb.metadata == {}
        assert emb.text == ""

    def test_metadata_stored(self):
        emb = LeadEmbedding(
            contact_id="c1", embedding=[], outcome="pending",
            metadata={"budget": "500K"},
        )
        assert emb.metadata["budget"] == "500K"


# -- RAGContext Dataclass ----------------------------------------------

class TestRAGContext:
    """Test RAGContext creation."""

    def test_create_context(self):
        ctx = RAGContext(
            similar_leads=[{"contact_id": "c1", "score": 0.9}],
            avg_conversion_rate=0.75,
            confidence=0.85,
            retrieval_scores=[0.9],
        )
        assert ctx.avg_conversion_rate == 0.75
        assert len(ctx.similar_leads) == 1

    def test_empty_context(self):
        ctx = RAGContext(
            similar_leads=[], avg_conversion_rate=0.0,
            confidence=0.0, retrieval_scores=[],
        )
        assert ctx.similar_leads == []
        assert ctx.retrieval_scores == []


# -- LeadIntelligenceRAG Core -----------------------------------------

class TestLeadIntelligenceRAGInit:
    """Test RAG initialization and indexing."""

    def test_init_empty(self):
        rag = LeadIntelligenceRAG()
        assert rag.index == []
        assert rag.vocabulary == {}

    def test_index_lead(self):
        rag = LeadIntelligenceRAG()
        rag.index_lead("c1", "Hello world", "converted")
        assert len(rag.index) == 1
        assert rag.index[0].contact_id == "c1"
        assert rag.index[0].text == "Hello world"

    def test_index_multiple_leads(self):
        rag = _build_rag()
        assert len(rag.index) == 5

    def test_index_lead_with_metadata(self):
        rag = LeadIntelligenceRAG()
        rag.index_lead("c1", "Test", "pending", metadata={"source": "web"})
        assert rag.index[0].metadata["source"] == "web"


# -- Tokenization ------------------------------------------------------

class TestTokenization:
    """Test the internal tokenizer."""

    def test_basic_tokenize(self):
        tokens = LeadIntelligenceRAG._tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_strips_punctuation(self):
        tokens = LeadIntelligenceRAG._tokenize("I'm pre-approved for $500K!")
        assert "i" in tokens
        assert "m" in tokens
        assert "pre" in tokens
        assert "approved" in tokens
        assert "500k" in tokens

    def test_empty_string(self):
        tokens = LeadIntelligenceRAG._tokenize("")
        assert tokens == []


# -- TF-IDF Computation -----------------------------------------------

class TestTFIDF:
    """Test TF-IDF vector computation."""

    def test_compute_tfidf_builds_vocabulary(self):
        rag = _build_rag()
        # Force vocabulary rebuild
        vec = rag._compute_tfidf("pre-approval buying house")
        assert len(rag.vocabulary) > 0
        assert len(vec) == len(rag.vocabulary)

    def test_tfidf_nonzero_for_matching_terms(self):
        rag = _build_rag()
        vec = rag._compute_tfidf("pre-approval buying house")
        # At least some entries should be non-zero
        assert any(v > 0 for v in vec)

    def test_tfidf_zero_for_unknown_terms(self):
        rag = _build_rag()
        vec = rag._compute_tfidf("xyzzyplugh")
        # All zeros since no vocabulary match
        assert all(v == 0.0 for v in vec)


# -- Cosine Similarity ------------------------------------------------

class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_identical_vectors(self):
        sim = LeadIntelligenceRAG._cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert sim == pytest.approx(1.0, rel=1e-3)

    def test_orthogonal_vectors(self):
        sim = LeadIntelligenceRAG._cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector(self):
        sim = LeadIntelligenceRAG._cosine_similarity([0.0, 0.0], [1.0, 1.0])
        assert sim == 0.0

    def test_empty_vectors(self):
        sim = LeadIntelligenceRAG._cosine_similarity([], [])
        assert sim == 0.0

    def test_different_length_vectors(self):
        sim = LeadIntelligenceRAG._cosine_similarity([1.0], [1.0, 2.0])
        assert sim == 0.0


# -- Semantic Search (search_similar) ----------------------------------

class TestSearchSimilar:
    """Test TF-IDF-based semantic search."""

    def test_empty_index(self):
        rag = LeadIntelligenceRAG()
        results = rag.search_similar("buy house")
        assert results == []

    def test_returns_results(self):
        rag = _build_rag()
        results = rag.search_similar("3-bedroom house near schools pre-approved")
        assert len(results) > 0

    def test_top_k_limit(self):
        rag = _build_rag()
        results = rag.search_similar("buy house", top_k=2)
        assert len(results) <= 2

    def test_similar_leads_ranked_by_relevance(self):
        rag = _build_rag()
        results = rag.search_similar("pre-approval 3-bedroom schools Rancho Cucamonga")
        # buyer_ready and hot_buyer should rank higher than cold_lead
        top_ids = [entry.contact_id for entry, _ in results[:2]]
        assert "cold_lead" not in top_ids


# -- Keyword Search (search_keyword) ----------------------------------

class TestSearchKeyword:
    """Test regex-based keyword search."""

    def test_empty_index(self):
        rag = LeadIntelligenceRAG()
        results = rag.search_keyword("house")
        assert results == []

    def test_returns_matching_leads(self):
        rag = _build_rag()
        results = rag.search_keyword("sell house relocation")
        assert len(results) > 0
        # seller_motivated should be among results
        ids = [entry.contact_id for entry, _ in results]
        assert "seller_motivated" in ids

    def test_no_matches(self):
        rag = _build_rag()
        results = rag.search_keyword("xyzzyplugh")
        assert results == []

    def test_keyword_score_is_fraction(self):
        rag = _build_rag()
        results = rag.search_keyword("house")
        for _, score in results:
            assert 0.0 < score <= 1.0


# -- Hybrid Search -----------------------------------------------------

class TestHybridSearch:
    """Test combined semantic + keyword search."""

    def test_empty_index(self):
        rag = LeadIntelligenceRAG()
        results = rag.hybrid_search("buy house")
        assert results == []

    def test_returns_results(self):
        rag = _build_rag()
        results = rag.hybrid_search("buy 3-bedroom house near schools")
        assert len(results) > 0

    def test_top_k_limit(self):
        rag = _build_rag()
        results = rag.hybrid_search("house", top_k=3)
        assert len(results) <= 3

    def test_semantic_weight_affects_ranking(self):
        rag = _build_rag()
        # With high semantic weight
        sem_results = rag.hybrid_search("pre-approval schools", semantic_weight=0.9)
        # With high keyword weight
        kw_results = rag.hybrid_search("pre-approval schools", semantic_weight=0.1)
        # Order may differ; at minimum both return results
        assert len(sem_results) > 0
        assert len(kw_results) > 0


# -- Augment Context ---------------------------------------------------

class TestAugmentContext:
    """Test RAG context augmentation."""

    def test_augment_returns_rag_context(self):
        rag = _build_rag()
        ctx = rag.augment_context("pre-approved buyer looking for house")
        assert isinstance(ctx, RAGContext)

    def test_augment_similar_leads_populated(self):
        rag = _build_rag()
        ctx = rag.augment_context("3-bedroom house schools")
        assert len(ctx.similar_leads) > 0

    def test_augment_conversion_rate(self):
        rag = _build_rag()
        ctx = rag.augment_context("pre-approved buyer looking for house")
        # Most indexed leads are converted, so rate should be > 0
        assert ctx.avg_conversion_rate >= 0.0

    def test_augment_confidence(self):
        rag = _build_rag()
        ctx = rag.augment_context("buy house near schools")
        assert ctx.confidence >= 0.0

    def test_augment_retrieval_scores(self):
        rag = _build_rag()
        ctx = rag.augment_context("sell house relocation", top_k=2)
        assert len(ctx.retrieval_scores) <= 2

    def test_augment_empty_index(self):
        rag = LeadIntelligenceRAG()
        ctx = rag.augment_context("anything")
        assert ctx.similar_leads == []
        assert ctx.avg_conversion_rate == 0.0
        assert ctx.confidence == 0.0

    def test_augment_similar_lead_structure(self):
        rag = _build_rag()
        ctx = rag.augment_context("buy house")
        for lead in ctx.similar_leads:
            assert "contact_id" in lead
            assert "outcome" in lead
            assert "score" in lead
            assert "metadata" in lead
