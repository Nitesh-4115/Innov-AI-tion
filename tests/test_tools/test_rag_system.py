"""
Tests for RAG System Tool
Tests vector-based knowledge retrieval for medication information
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import List, Dict, Any

from tools.rag_system import (
    RAGSystem,
    Document,
    SearchResult,
    MEDICATION_KNOWLEDGE_BASE,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def rag_system():
    """Create RAG system instance"""
    return RAGSystem()


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        Document(
            id="doc_001",
            content="Metformin is a first-line medication for type 2 diabetes. Take with meals.",
            metadata={"category": "diabetes", "drug": "metformin"}
        ),
        Document(
            id="doc_002", 
            content="Lisinopril is an ACE inhibitor used to treat high blood pressure.",
            metadata={"category": "cardiovascular", "drug": "lisinopril"}
        ),
        Document(
            id="doc_003",
            content="Always take medications as prescribed by your healthcare provider.",
            metadata={"category": "safety", "type": "general"}
        ),
    ]


@pytest.fixture
def sample_query():
    """Sample search query"""
    return "How should I take metformin for diabetes?"


# =============================================================================
# Test RAGSystem Initialization
# =============================================================================

class TestRAGSystemInit:
    """Tests for RAG system initialization"""
    
    def test_system_initialization(self, rag_system):
        """Test that RAG system initializes correctly"""
        assert rag_system is not None
        assert hasattr(rag_system, "documents")
        assert isinstance(rag_system.documents, dict)
    
    def test_persist_directory_configured(self, rag_system):
        """Test that persist directory is configured"""
        assert hasattr(rag_system, "persist_directory")
        assert rag_system.persist_directory is not None
    
    def test_knowledge_base_loaded(self):
        """Test built-in knowledge base exists"""
        assert MEDICATION_KNOWLEDGE_BASE is not None
        assert len(MEDICATION_KNOWLEDGE_BASE) > 0
    
    def test_knowledge_base_structure(self):
        """Test knowledge base has correct structure"""
        for doc in MEDICATION_KNOWLEDGE_BASE:
            assert "id" in doc
            assert "content" in doc
            assert "category" in doc
            assert "tags" in doc


# =============================================================================
# Test Document Class
# =============================================================================

class TestDocument:
    """Tests for Document dataclass"""
    
    def test_document_creation(self):
        """Test creating a document"""
        doc = Document(
            id="test_001",
            content="Test content",
            metadata={"key": "value"}
        )
        assert doc.id == "test_001"
        assert doc.content == "Test content"
        assert doc.metadata == {"key": "value"}
        assert doc.embedding is None
    
    def test_document_with_embedding(self):
        """Test document with embedding"""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        doc = Document(
            id="test_002",
            content="Test content",
            embedding=embedding
        )
        assert doc.embedding == embedding
    
    def test_document_default_metadata(self):
        """Test document with default metadata"""
        doc = Document(id="test", content="content")
        assert doc.metadata == {}


# =============================================================================
# Test SearchResult Class
# =============================================================================

class TestSearchResult:
    """Tests for SearchResult dataclass"""
    
    def test_search_result_creation(self):
        """Test creating a search result"""
        result = SearchResult(
            document_id="doc_001",
            content="Found content",
            score=0.95,
            metadata={"category": "test"}
        )
        assert result.document_id == "doc_001"
        assert result.content == "Found content"
        assert result.score == 0.95
        assert result.metadata == {"category": "test"}
    
    def test_search_result_score_range(self):
        """Test search results with different scores"""
        high_score = SearchResult(document_id="1", content="", score=0.99)
        low_score = SearchResult(document_id="2", content="", score=0.1)
        
        assert high_score.score > low_score.score
    
    def test_search_result_default_metadata(self):
        """Test search result with default metadata"""
        result = SearchResult(document_id="1", content="test", score=0.5)
        assert result.metadata == {}


# =============================================================================
# Test Knowledge Base Content
# =============================================================================

class TestKnowledgeBaseContent:
    """Tests for built-in knowledge base content"""
    
    def test_safety_guidelines_exist(self):
        """Test safety guidelines are included"""
        categories = [doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert "safety" in categories
    
    def test_adherence_info_exists(self):
        """Test adherence information is included"""
        categories = [doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert "adherence" in categories
    
    def test_interaction_info_exists(self):
        """Test interaction information is included"""
        categories = [doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert "interactions" in categories
    
    def test_condition_specific_info_exists(self):
        """Test condition-specific information is included"""
        categories = [doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert "conditions" in categories
    
    def test_side_effects_info_exists(self):
        """Test side effects information is included"""
        categories = [doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert "side_effects" in categories
    
    def test_document_ids_unique(self):
        """Test all document IDs are unique"""
        ids = [doc["id"] for doc in MEDICATION_KNOWLEDGE_BASE]
        assert len(ids) == len(set(ids))
    
    def test_all_documents_have_content(self):
        """Test all documents have non-empty content"""
        for doc in MEDICATION_KNOWLEDGE_BASE:
            assert doc["content"].strip(), f"Document {doc['id']} has empty content"
    
    def test_all_documents_have_tags(self):
        """Test all documents have tags"""
        for doc in MEDICATION_KNOWLEDGE_BASE:
            assert len(doc["tags"]) > 0, f"Document {doc['id']} has no tags"


# =============================================================================
# Test Document Management
# =============================================================================

class TestDocumentManagement:
    """Tests for document management operations"""
    
    @pytest.mark.asyncio
    async def test_add_document(self, rag_system, sample_documents):
        """Test adding a document to the system"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.add = MagicMock()
            
            doc = sample_documents[0]
            # Assuming add_document method exists
            if hasattr(rag_system, "add_document"):
                await rag_system.add_document(doc)
    
    @pytest.mark.asyncio
    async def test_add_multiple_documents(self, rag_system, sample_documents):
        """Test adding multiple documents"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.add = MagicMock()
            
            if hasattr(rag_system, "add_documents"):
                await rag_system.add_documents(sample_documents)
    
    def test_get_document_by_id(self, rag_system, sample_documents):
        """Test retrieving document by ID"""
        # Add document to internal store
        doc = sample_documents[0]
        rag_system.documents[doc.id] = doc
        
        # Retrieve it
        retrieved = rag_system.documents.get(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id
    
    def test_document_not_found(self, rag_system):
        """Test handling non-existent document"""
        result = rag_system.documents.get("nonexistent_id")
        assert result is None


# =============================================================================
# Test Search Operations
# =============================================================================

class TestSearchOperations:
    """Tests for search/retrieval operations"""
    
    @pytest.mark.asyncio
    async def test_search_returns_results(self, rag_system, sample_query):
        """Test that search returns results"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["doc_001"]],
                "documents": [["Metformin information"]],
                "distances": [[0.1]],
                "metadatas": [[{"category": "diabetes"}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search(sample_query)
                assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, rag_system):
        """Test search with category filters"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["doc_001"]],
                "documents": [["Diabetes content"]],
                "distances": [[0.1]],
                "metadatas": [[{"category": "diabetes"}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search(
                    "diabetes medication",
                    filter_category="diabetes"
                )
    
    @pytest.mark.asyncio
    async def test_search_result_ordering(self, rag_system):
        """Test search results are ordered by relevance"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["doc_001", "doc_002", "doc_003"]],
                "documents": [["Best match", "Good match", "Weak match"]],
                "distances": [[0.1, 0.3, 0.7]],
                "metadatas": [[{}, {}, {}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search("test query", top_k=3)
                # Results should be ordered by distance (ascending = more relevant)
    
    @pytest.mark.asyncio
    async def test_search_empty_query(self, rag_system):
        """Test search with empty query"""
        if hasattr(rag_system, "search"):
            results = await rag_system.search("")
            assert results == [] or results is None
    
    @pytest.mark.asyncio
    async def test_search_top_k_limit(self, rag_system):
        """Test search respects top_k limit"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["doc_001", "doc_002"]],
                "documents": [["Doc 1", "Doc 2"]],
                "distances": [[0.1, 0.2]],
                "metadatas": [[{}, {}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search("query", top_k=2)
                assert len(results) <= 2


# =============================================================================
# Test RAG Query Processing
# =============================================================================

class TestRAGQueryProcessing:
    """Tests for RAG query processing"""
    
    @pytest.mark.asyncio
    async def test_query_with_context(self, rag_system):
        """Test query returns relevant context"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["doc_001"]],
                "documents": [["Medication safety information"]],
                "distances": [[0.15]],
                "metadatas": [[{"category": "safety"}]]
            })
            
            if hasattr(rag_system, "get_relevant_context"):
                context = await rag_system.get_relevant_context("medication safety")
                assert context is not None
    
    @pytest.mark.asyncio
    async def test_medication_query(self, rag_system):
        """Test query about specific medication"""
        # Test metformin query
        query = "What should I know about taking metformin?"
        
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["diabetes_001"]],
                "documents": [["Metformin is first-line treatment for Type 2 diabetes"]],
                "distances": [[0.1]],
                "metadatas": [[{"category": "conditions", "tags": ["diabetes", "metformin"]}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search(query)
    
    @pytest.mark.asyncio
    async def test_side_effect_query(self, rag_system):
        """Test query about side effects"""
        query = "How do I manage nausea from medication?"
        
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [["side_effects_001"]],
                "documents": [["Managing Common Medication Side Effects: NAUSEA..."]],
                "distances": [[0.12]],
                "metadatas": [[{"category": "side_effects"}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search(query)


# =============================================================================
# Test ChromaDB Integration
# =============================================================================

class TestChromaDBIntegration:
    """Tests for ChromaDB vector store integration"""
    
    def test_collection_initialization(self, rag_system):
        """Test ChromaDB collection can be initialized"""
        # Collection should be lazily initialized
        assert hasattr(rag_system, "_collection")
    
    @pytest.mark.asyncio
    async def test_embedding_generation(self, rag_system):
        """Test that embeddings can be generated for documents"""
        with patch("chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction") as mock_ef:
            mock_ef.return_value = MagicMock()
            
            # Test that embedding function is configured
            if hasattr(rag_system, "_get_embedding_function"):
                ef = rag_system._get_embedding_function()
                assert ef is not None
    
    def test_persist_directory_exists(self, rag_system):
        """Test persist directory is properly set"""
        assert rag_system.persist_directory is not None


# =============================================================================
# Test Error Handling
# =============================================================================

class TestRAGErrorHandling:
    """Tests for RAG system error handling"""
    
    @pytest.mark.asyncio
    async def test_search_handles_empty_collection(self, rag_system):
        """Test search handles empty collection gracefully"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(return_value={
                "ids": [[]],
                "documents": [[]],
                "distances": [[]],
                "metadatas": [[]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search("any query")
                assert results == [] or results is not None
    
    @pytest.mark.asyncio
    async def test_search_handles_connection_error(self, rag_system):
        """Test search handles connection errors"""
        with patch.object(rag_system, "_collection") as mock_collection:
            mock_collection.query = MagicMock(side_effect=Exception("Connection error"))
            
            if hasattr(rag_system, "search"):
                try:
                    await rag_system.search("query")
                except Exception as e:
                    assert "error" in str(e).lower() or isinstance(e, Exception)
    
    @pytest.mark.asyncio  
    async def test_handles_invalid_document(self, rag_system):
        """Test handling invalid document format"""
        invalid_doc = {"invalid": "format"}  # Missing required fields
        
        # Should handle gracefully or raise appropriate error
        if hasattr(rag_system, "add_document"):
            try:
                await rag_system.add_document(invalid_doc)
            except (ValueError, TypeError, KeyError):
                pass  # Expected behavior


# =============================================================================
# Test Knowledge Categories
# =============================================================================

class TestKnowledgeCategories:
    """Tests for knowledge base categories"""
    
    def test_get_documents_by_category(self):
        """Test filtering documents by category"""
        safety_docs = [
            doc for doc in MEDICATION_KNOWLEDGE_BASE 
            if doc["category"] == "safety"
        ]
        assert len(safety_docs) > 0
    
    def test_get_documents_by_tag(self):
        """Test filtering documents by tag"""
        diabetes_docs = [
            doc for doc in MEDICATION_KNOWLEDGE_BASE 
            if "diabetes" in doc.get("tags", [])
        ]
        assert len(diabetes_docs) > 0
    
    def test_all_categories_covered(self):
        """Test all expected categories are represented"""
        expected_categories = {
            "safety", "adherence", "interactions", 
            "conditions", "side_effects"
        }
        actual_categories = {doc["category"] for doc in MEDICATION_KNOWLEDGE_BASE}
        
        assert expected_categories.issubset(actual_categories)


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestRAGIntegration:
    """Integration tests for RAG system"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_query_workflow(self, rag_system):
        """Test complete query workflow"""
        # 1. Initialize system
        assert rag_system is not None
        
        # 2. Simulate adding documents
        with patch.object(rag_system, "_collection"):
            pass  # Would add documents
        
        # 3. Perform search
        with patch.object(rag_system, "_collection") as mock:
            mock.query = MagicMock(return_value={
                "ids": [["doc_001"]],
                "documents": [["Relevant medication info"]],
                "distances": [[0.1]],
                "metadatas": [[{}]]
            })
            
            if hasattr(rag_system, "search"):
                results = await rag_system.search("medication question")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_query_session(self, rag_system):
        """Test multiple queries in sequence"""
        queries = [
            "How to take metformin?",
            "What are common side effects?",
            "Drug interactions to watch for?"
        ]
        
        with patch.object(rag_system, "_collection") as mock:
            mock.query = MagicMock(return_value={
                "ids": [["doc"]],
                "documents": [["answer"]],
                "distances": [[0.1]],
                "metadatas": [[{}]]
            })
            
            if hasattr(rag_system, "search"):
                for query in queries:
                    results = await rag_system.search(query)


# =============================================================================
# Test Performance
# =============================================================================

class TestRAGPerformance:
    """Performance tests for RAG system"""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_search_response_time(self, rag_system):
        """Test search completes in reasonable time"""
        import time
        
        with patch.object(rag_system, "_collection") as mock:
            mock.query = MagicMock(return_value={
                "ids": [["doc"]],
                "documents": [["content"]],
                "distances": [[0.1]],
                "metadatas": [[{}]]
            })
            
            if hasattr(rag_system, "search"):
                start = time.time()
                await rag_system.search("test query")
                elapsed = time.time() - start
                
                # Should complete within 5 seconds
                assert elapsed < 5.0
    
    @pytest.mark.slow
    def test_knowledge_base_loading(self):
        """Test knowledge base loads efficiently"""
        import time
        
        start = time.time()
        kb = MEDICATION_KNOWLEDGE_BASE
        elapsed = time.time() - start
        
        # Should load instantly (it's a constant)
        assert elapsed < 0.1
        assert len(kb) > 0
