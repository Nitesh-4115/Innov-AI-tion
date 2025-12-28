"""
Vector Store
ChromaDB-based vector store for RAG (Retrieval Augmented Generation)
"""

import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import hashlib

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Document:
    """Document with content and metadata"""
    content: str
    metadata: Dict[str, Any]
    id: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            # Generate ID from content hash
            self.id = hashlib.md5(self.content.encode()).hexdigest()[:16]


@dataclass
class SearchResult:
    """Search result with document and score"""
    document: Document
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.document.content,
            "metadata": self.document.metadata,
            "score": self.score
        }


class VectorStore:
    """
    Vector store for semantic search using ChromaDB
    
    Used for:
    - Clinical guidelines retrieval
    - Drug information search
    - Symptom-medication correlation lookup
    """
    
    def __init__(
        self,
        collection_name: str = "adherence_guardian",
        persist_directory: Optional[str] = None
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization of ChromaDB and embedding model"""
        if self._initialized:
            return
        
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available. Vector store will use fallback search.")
            self._initialized = True
            return
        
        try:
            # Ensure persist directory exists
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Initialize ChromaDB client
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"Initialized vector store: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
        
        # Initialize embedding model
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info(f"Loaded embedding model: {settings.EMBEDDING_MODEL}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
        
        self._initialized = True
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts"""
        if self._embedding_model is None:
            # Return empty embeddings if model not available
            return [[0.0] * 384 for _ in texts]  # Default dimension
        
        try:
            embeddings = self._embedding_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return [[0.0] * 384 for _ in texts]
    
    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 100
    ) -> int:
        """
        Add documents to the vector store
        
        Args:
            documents: List of documents to add
            batch_size: Batch size for insertion
            
        Returns:
            Number of documents added
        """
        self._ensure_initialized()
        
        if not self._collection:
            logger.warning("Vector store not available, skipping add")
            return 0
        
        added = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            ids = [doc.id for doc in batch]
            contents = [doc.content for doc in batch]
            # Filter out None values from metadata - ChromaDB doesn't accept None
            metadatas = [
                {k: v for k, v in doc.metadata.items() if v is not None}
                for doc in batch
            ]
            
            # Generate embeddings
            embeddings = self._get_embeddings(contents)
            
            try:
                self._collection.add(
                    ids=ids,
                    documents=contents,
                    metadatas=metadatas,
                    embeddings=embeddings
                )
                added += len(batch)
            except Exception as e:
                logger.error(f"Failed to add batch: {e}")
        
        logger.info(f"Added {added} documents to vector store")
        return added
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of search results
        """
        self._ensure_initialized()
        
        if not self._collection:
            return self._fallback_search(query, n_results)
        
        try:
            # Generate query embedding
            query_embedding = self._get_embeddings([query])[0]
            
            # Search
            where_filter = filter_metadata if filter_metadata else None
            
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert to SearchResult objects
            search_results = []
            
            if results and results['documents']:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity score (cosine)
                    score = 1 - distance
                    
                    search_results.append(SearchResult(
                        document=Document(
                            content=doc,
                            metadata=metadata,
                            id=results['ids'][0][i] if results['ids'] else None
                        ),
                        score=score
                    ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return self._fallback_search(query, n_results)
    
    def _fallback_search(
        self,
        query: str,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Fallback keyword-based search when vector store unavailable"""
        # This is a simple fallback - in production, you'd want better handling
        return []
    
    def delete_documents(
        self,
        ids: Optional[List[str]] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Delete documents from the store"""
        self._ensure_initialized()
        
        if not self._collection:
            return 0
        
        try:
            if ids:
                self._collection.delete(ids=ids)
                return len(ids)
            elif filter_metadata:
                self._collection.delete(where=filter_metadata)
                return -1  # Unknown count
            return 0
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID"""
        self._ensure_initialized()
        
        if not self._collection:
            return None
        
        try:
            result = self._collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if result and result['documents']:
                return Document(
                    content=result['documents'][0],
                    metadata=result['metadatas'][0],
                    id=doc_id
                )
            return None
        except Exception as e:
            logger.error(f"Get document failed: {e}")
            return None
    
    def count(self) -> int:
        """Get document count"""
        self._ensure_initialized()
        
        if not self._collection:
            return 0
        
        try:
            return self._collection.count()
        except Exception:
            return 0
    
    def clear(self):
        """Clear all documents from the collection"""
        self._ensure_initialized()
        
        if self._client and self._collection:
            try:
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Cleared vector store: {self.collection_name}")
            except Exception as e:
                logger.error(f"Clear failed: {e}")


class KnowledgeBaseStore:
    """
    Specialized vector store for medication adherence knowledge base
    
    Collections:
    - clinical_guidelines: Clinical practice guidelines
    - drug_info: Drug information and interactions
    - adherence_tips: Adherence improvement strategies
    - side_effects: Side effect information
    """
    
    def __init__(self):
        self.guidelines_store = VectorStore("clinical_guidelines")
        self.drug_store = VectorStore("drug_info")
        self.tips_store = VectorStore("adherence_tips")
        self.side_effects_store = VectorStore("side_effects")
    
    def add_guideline(
        self,
        content: str,
        condition: str,
        source: str,
        year: Optional[int] = None
    ) -> str:
        """Add a clinical guideline"""
        doc = Document(
            content=content,
            metadata={
                "type": "guideline",
                "condition": condition,
                "source": source,
                "year": year or 2024
            }
        )
        self.guidelines_store.add_documents([doc])
        return doc.id
    
    def add_drug_info(
        self,
        content: str,
        drug_name: str,
        drug_class: Optional[str] = None,
        rxnorm_id: Optional[str] = None
    ) -> str:
        """Add drug information"""
        doc = Document(
            content=content,
            metadata={
                "type": "drug_info",
                "drug_name": drug_name,
                "drug_class": drug_class,
                "rxnorm_id": rxnorm_id
            }
        )
        self.drug_store.add_documents([doc])
        return doc.id
    
    def add_adherence_tip(
        self,
        content: str,
        barrier_type: str,
        effectiveness_score: float = 0.5
    ) -> str:
        """Add an adherence tip"""
        doc = Document(
            content=content,
            metadata={
                "type": "adherence_tip",
                "barrier_type": barrier_type,
                "effectiveness": effectiveness_score
            }
        )
        self.tips_store.add_documents([doc])
        return doc.id
    
    def add_side_effect_info(
        self,
        content: str,
        drug_name: str,
        side_effect: str,
        frequency: str = "common"
    ) -> str:
        """Add side effect information"""
        doc = Document(
            content=content,
            metadata={
                "type": "side_effect",
                "drug_name": drug_name,
                "side_effect": side_effect,
                "frequency": frequency
            }
        )
        self.side_effects_store.add_documents([doc])
        return doc.id
    
    def search_guidelines(
        self,
        query: str,
        condition: Optional[str] = None,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Search clinical guidelines"""
        filter_meta = {"condition": condition} if condition else None
        return self.guidelines_store.search(query, n_results, filter_meta)
    
    def search_drug_info(
        self,
        query: str,
        drug_name: Optional[str] = None,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Search drug information"""
        filter_meta = {"drug_name": drug_name} if drug_name else None
        return self.drug_store.search(query, n_results, filter_meta)
    
    def search_adherence_tips(
        self,
        query: str,
        barrier_type: Optional[str] = None,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Search adherence tips"""
        filter_meta = {"barrier_type": barrier_type} if barrier_type else None
        return self.tips_store.search(query, n_results, filter_meta)
    
    def search_side_effects(
        self,
        query: str,
        drug_name: Optional[str] = None,
        n_results: int = 5
    ) -> List[SearchResult]:
        """Search side effect information"""
        filter_meta = {"drug_name": drug_name} if drug_name else None
        return self.side_effects_store.search(query, n_results, filter_meta)
    
    def multi_search(
        self,
        query: str,
        n_results: int = 3
    ) -> Dict[str, List[SearchResult]]:
        """Search across all knowledge bases"""
        return {
            "guidelines": self.search_guidelines(query, n_results=n_results),
            "drug_info": self.search_drug_info(query, n_results=n_results),
            "adherence_tips": self.search_adherence_tips(query, n_results=n_results),
            "side_effects": self.search_side_effects(query, n_results=n_results)
        }


# Singleton instances
vector_store = VectorStore()
knowledge_base = KnowledgeBaseStore()
