"""
RAG (Retrieval Augmented Generation) System
Vector-based knowledge retrieval for medication and health information
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib

from config import settings


logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document in the knowledge base"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass 
class SearchResult:
    """Search result from the knowledge base"""
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# Built-in medication knowledge base
MEDICATION_KNOWLEDGE_BASE = [
    # General medication safety
    {
        "id": "med_safety_001",
        "content": """
        General Medication Safety Guidelines:
        1. Always take medications as prescribed by your healthcare provider
        2. Never share prescription medications with others
        3. Store medications properly - check labels for temperature requirements
        4. Keep medications in original containers with labels intact
        5. Check expiration dates regularly and dispose of expired medications properly
        6. Keep a current list of all medications including OTC drugs and supplements
        7. Inform all healthcare providers about all medications you take
        8. Never crush, split, or chew medications without checking with pharmacist first
        """,
        "category": "safety",
        "tags": ["general", "storage", "safety"]
    },
    
    # Adherence importance
    {
        "id": "adherence_001",
        "content": """
        Why Medication Adherence Matters:
        - Medications work best when taken consistently as prescribed
        - Skipping doses can lead to treatment failure
        - Inconsistent use of antibiotics can promote antibiotic resistance
        - Blood pressure and diabetes medications need consistent levels to be effective
        - Missing doses of psychiatric medications can cause withdrawal or relapse
        - Some medications need to build up in your system over time
        - Adherence rates of 80% or higher are typically needed for effectiveness
        """,
        "category": "adherence",
        "tags": ["importance", "effectiveness", "consistency"]
    },
    
    # Missed dose guidance
    {
        "id": "missed_dose_001",
        "content": """
        General Guidance for Missed Doses:
        - If you miss a dose and remember within a few hours, take it as soon as you remember
        - If it's almost time for your next dose, skip the missed dose
        - Never take a double dose to make up for a missed one
        - For time-sensitive medications (like certain antibiotics), timing matters more
        - Contact your healthcare provider if you miss multiple doses
        - Set reminders to help prevent missed doses in the future
        - Some medications have specific instructions for missed doses - check with pharmacist
        """,
        "category": "adherence",
        "tags": ["missed_dose", "guidance", "timing"]
    },
    
    # Food and medication interactions
    {
        "id": "food_interaction_001",
        "content": """
        Food and Medication Interactions:
        
        TAKE WITH FOOD:
        - NSAIDs (ibuprofen, naproxen) - reduces stomach irritation
        - Metformin - reduces GI side effects
        - Corticosteroids (prednisone) - reduces stomach upset
        
        TAKE ON EMPTY STOMACH:
        - Levothyroxine - take 30-60 minutes before breakfast
        - Bisphosphonates (alendronate) - take with water only, 30 min before food
        - Many antibiotics - food can reduce absorption
        
        AVOID SPECIFIC FOODS:
        - Warfarin + Vitamin K rich foods (leafy greens) - maintain consistent intake
        - Statins + Grapefruit - can increase drug levels dangerously
        - MAO inhibitors + Tyramine foods (aged cheese, wine) - hypertensive crisis risk
        - Tetracycline + Dairy - reduces absorption
        """,
        "category": "interactions",
        "tags": ["food", "timing", "absorption"]
    },
    
    # Common side effects management
    {
        "id": "side_effects_001",
        "content": """
        Managing Common Medication Side Effects:
        
        NAUSEA:
        - Take medication with food if allowed
        - Take at bedtime if once-daily
        - Eat smaller, more frequent meals
        - Avoid lying down immediately after taking
        
        DIZZINESS:
        - Rise slowly from sitting or lying positions
        - Avoid driving until you know how medication affects you
        - Stay hydrated
        - May improve after body adjusts to medication
        
        DROWSINESS:
        - Take at bedtime if possible
        - Avoid alcohol
        - Don't drive or operate machinery until effects known
        - Usually improves over time
        
        CONSTIPATION:
        - Increase water intake
        - Add fiber to diet
        - Exercise regularly
        - Consider stool softener (ask pharmacist)
        
        DRY MOUTH:
        - Sip water frequently
        - Chew sugar-free gum
        - Avoid caffeine and alcohol
        - Use saliva substitutes if severe
        """,
        "category": "side_effects",
        "tags": ["management", "common", "tips"]
    },
    
    # Diabetes medications
    {
        "id": "diabetes_001",
        "content": """
        Diabetes Medication Information:
        
        METFORMIN (Glucophage):
        - First-line treatment for Type 2 diabetes
        - Take with meals to reduce stomach upset
        - Common side effects: nausea, diarrhea (usually improve over time)
        - IMPORTANT: Hold before contrast procedures
        - Does not cause hypoglycemia when used alone
        
        INSULIN:
        - Various types with different onset and duration
        - Proper injection technique is important
        - Rotate injection sites
        - Monitor blood sugar regularly
        - Know symptoms of hypoglycemia
        
        GLP-1 AGONISTS (semaglutide, liraglutide):
        - Help with blood sugar and weight
        - Injected weekly or daily depending on type
        - Start with low dose and increase gradually
        - Nausea common initially but usually improves
        """,
        "category": "conditions",
        "tags": ["diabetes", "metformin", "insulin"]
    },
    
    # Blood pressure medications
    {
        "id": "bp_meds_001",
        "content": """
        Blood Pressure Medication Information:
        
        ACE INHIBITORS (lisinopril, enalapril):
        - Protect heart and kidneys
        - Common side effect: dry cough (switch to ARB if problematic)
        - Monitor potassium levels
        - Avoid if pregnant
        - Watch for facial/throat swelling (rare but serious)
        
        ARBs (losartan, valsartan):
        - Alternative to ACE inhibitors
        - Generally better tolerated (less cough)
        - Similar benefits for heart and kidneys
        - Avoid if pregnant
        
        BETA BLOCKERS (metoprolol, atenolol):
        - Slow heart rate, reduce blood pressure
        - Don't stop suddenly - must taper
        - May mask symptoms of low blood sugar
        - Can cause fatigue, cold hands/feet
        
        CALCIUM CHANNEL BLOCKERS (amlodipine):
        - Common side effect: ankle swelling
        - Generally well-tolerated
        - Take consistently at same time daily
        """,
        "category": "conditions",
        "tags": ["hypertension", "blood_pressure", "cardiovascular"]
    },
    
    # Cholesterol medications
    {
        "id": "cholesterol_001",
        "content": """
        Cholesterol Medication Information:
        
        STATINS (atorvastatin, simvastatin, rosuvastatin):
        - Most effective for lowering LDL cholesterol
        - Reduce cardiovascular risk significantly
        - Take in evening (cholesterol synthesis highest at night)
        - Avoid grapefruit (increases drug levels)
        
        SIDE EFFECTS TO WATCH:
        - Muscle pain/weakness - report to provider
        - Liver effects - periodic monitoring may be needed
        - Memory issues (rare) - usually reversible
        
        WHEN TO SEEK HELP:
        - Severe muscle pain, especially with dark urine
        - Unexplained muscle weakness
        - Yellowing of skin or eyes
        """,
        "category": "conditions",
        "tags": ["cholesterol", "statins", "cardiovascular"]
    },
    
    # Mental health medications
    {
        "id": "mental_health_001",
        "content": """
        Mental Health Medication Information:
        
        SSRIs (sertraline, fluoxetine, escitalopram):
        - Used for depression and anxiety
        - Take 4-6 weeks to reach full effect
        - Don't stop suddenly - must taper
        - Common initial side effects usually improve
        
        IMPORTANT WARNINGS:
        - Increased suicidal thoughts possible in young adults initially
        - Serotonin syndrome risk if combined with other serotonergic drugs
        - Avoid alcohol
        - Tell provider about all other medications
        
        WHAT TO EXPECT:
        - Week 1-2: Side effects may occur (nausea, headache)
        - Week 2-4: Some improvement may begin
        - Week 4-8: Full therapeutic effect develops
        - Continue even when feeling better
        """,
        "category": "conditions",
        "tags": ["mental_health", "antidepressants", "ssri"]
    },
    
    # Pain medications
    {
        "id": "pain_001",
        "content": """
        Pain Medication Safety:
        
        NSAIDs (ibuprofen, naproxen):
        - Take with food to protect stomach
        - Avoid if history of stomach ulcers or bleeding
        - Can affect kidney function with long-term use
        - Interact with blood thinners
        - Maximum daily doses should not be exceeded
        
        ACETAMINOPHEN (Tylenol):
        - Generally safer for stomach
        - Watch for hidden sources in combination products
        - Maximum 3,000-4,000mg daily
        - Liver damage risk with excess or alcohol use
        
        OPIOIDS:
        - Take exactly as prescribed
        - Never share with others
        - Store securely
        - Risk of dependence with long-term use
        - Don't combine with alcohol or sedatives
        - Can cause constipation, drowsiness
        """,
        "category": "conditions",
        "tags": ["pain", "nsaids", "opioids", "safety"]
    },
    
    # Medication storage
    {
        "id": "storage_001",
        "content": """
        Proper Medication Storage:
        
        GENERAL RULES:
        - Cool, dry place away from sunlight
        - Not in bathroom (too humid)
        - Out of reach of children and pets
        - Keep in original containers
        
        REFRIGERATED MEDICATIONS:
        - Some insulins (check label)
        - Certain eye drops
        - Some antibiotics when reconstituted
        - Don't freeze unless specified
        
        TEMPERATURE-SENSITIVE:
        - Insulin: Refrigerate unopened; room temp once opened
        - Nitroglycerin: Room temperature, dark container
        - Suppositories: May need refrigeration
        
        DISPOSAL:
        - Don't flush most medications
        - Use pharmacy take-back programs
        - Mix with coffee grounds or cat litter if no take-back available
        - Remove personal information from containers
        """,
        "category": "safety",
        "tags": ["storage", "disposal", "temperature"]
    }
]


class RAGSystem:
    """
    Retrieval Augmented Generation system for medication knowledge
    """
    
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.persist_directory = Path(settings.CHROMA_PERSIST_DIRECTORY)
        self._chroma_client = None
        self._collection = None
        self._embedder = None
        
        # Load built-in knowledge base
        self._load_builtin_knowledge()
    
    def _load_builtin_knowledge(self):
        """Load the built-in medication knowledge base"""
        for doc_data in MEDICATION_KNOWLEDGE_BASE:
            doc = Document(
                id=doc_data["id"],
                content=doc_data["content"].strip(),
                metadata={
                    "category": doc_data.get("category", "general"),
                    "tags": doc_data.get("tags", []),
                    "source": "builtin"
                }
            )
            self.documents[doc.id] = doc
        
        logger.info(f"Loaded {len(self.documents)} built-in documents")
    
    async def initialize(self):
        """Initialize vector database and embeddings"""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            # Create persist directory
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB
            self._chroma_client = chromadb.Client(ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_directory),
                anonymized_telemetry=False
            ))
            
            # Get or create collection
            self._collection = self._chroma_client.get_or_create_collection(
                name="medication_knowledge",
                metadata={"description": "Medication and health knowledge base"}
            )
            
            # Index built-in documents if not already indexed
            await self._index_documents()
            
            logger.info("RAG system initialized successfully")
            
        except ImportError:
            logger.warning("ChromaDB not installed. Using simple keyword search.")
        except Exception as e:
            logger.error(f"Error initializing RAG system: {e}")
    
    async def _index_documents(self):
        """Index documents into vector database"""
        if not self._collection:
            return
        
        # Check what's already indexed
        existing = self._collection.get()
        existing_ids = set(existing.get("ids", []))
        
        # Index new documents
        new_docs = [doc for doc in self.documents.values() if doc.id not in existing_ids]
        
        if new_docs:
            self._collection.add(
                ids=[doc.id for doc in new_docs],
                documents=[doc.content for doc in new_docs],
                metadatas=[doc.metadata for doc in new_docs]
            )
            logger.info(f"Indexed {len(new_docs)} new documents")
    
    async def search(
        self,
        query: str,
        n_results: int = 5,
        category_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search the knowledge base
        
        Args:
            query: Search query
            n_results: Maximum number of results
            category_filter: Filter by category
            tags_filter: Filter by tags
            
        Returns:
            List of SearchResult objects
        """
        # Try vector search first
        if self._collection:
            try:
                where_filter = {}
                if category_filter:
                    where_filter["category"] = category_filter
                
                results = self._collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter if where_filter else None
                )
                
                search_results = []
                for i, doc_id in enumerate(results["ids"][0]):
                    search_results.append(SearchResult(
                        document_id=doc_id,
                        content=results["documents"][0][i],
                        score=1 - (results["distances"][0][i] if results.get("distances") else 0),
                        metadata=results["metadatas"][0][i] if results.get("metadatas") else {}
                    ))
                
                return search_results
                
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to keyword: {e}")
        
        # Fallback to keyword search
        return self._keyword_search(query, n_results, category_filter, tags_filter)
    
    def _keyword_search(
        self,
        query: str,
        n_results: int,
        category_filter: Optional[str],
        tags_filter: Optional[List[str]]
    ) -> List[SearchResult]:
        """Simple keyword-based search fallback"""
        query_terms = query.lower().split()
        scored_docs = []
        
        for doc in self.documents.values():
            # Apply filters
            if category_filter and doc.metadata.get("category") != category_filter:
                continue
            
            if tags_filter:
                doc_tags = doc.metadata.get("tags", [])
                if not any(tag in doc_tags for tag in tags_filter):
                    continue
            
            # Score based on term frequency
            content_lower = doc.content.lower()
            score = sum(content_lower.count(term) for term in query_terms)
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # Sort by score and return top results
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [
            SearchResult(
                document_id=doc.id,
                content=doc.content,
                score=score / 100,  # Normalize
                metadata=doc.metadata
            )
            for doc, score in scored_docs[:n_results]
        ]
    
    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 2000
    ) -> str:
        """
        Get relevant context for a query (for LLM augmentation)
        
        Args:
            query: The query to find context for
            max_tokens: Maximum approximate tokens to return
            
        Returns:
            Concatenated relevant context
        """
        results = await self.search(query, n_results=3)
        
        context_parts = []
        total_length = 0
        max_chars = max_tokens * 4  # Rough estimate
        
        for result in results:
            if total_length + len(result.content) > max_chars:
                break
            
            context_parts.append(f"[Source: {result.metadata.get('category', 'general')}]\n{result.content}")
            total_length += len(result.content)
        
        return "\n\n---\n\n".join(context_parts)
    
    async def add_document(
        self,
        content: str,
        category: str = "custom",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a new document to the knowledge base
        
        Args:
            content: Document content
            category: Document category
            tags: Document tags
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        # Generate ID from content hash
        doc_id = hashlib.md5(content.encode()).hexdigest()[:12]
        
        doc_metadata = {
            "category": category,
            "tags": tags or [],
            "source": "custom",
            **(metadata or {})
        }
        
        doc = Document(
            id=doc_id,
            content=content,
            metadata=doc_metadata
        )
        
        self.documents[doc_id] = doc
        
        # Index if vector store available
        if self._collection:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[doc_metadata]
            )
        
        return doc_id
    
    async def get_medication_info(self, medication_name: str) -> Optional[str]:
        """Get information about a specific medication"""
        results = await self.search(
            f"{medication_name} medication information side effects dosage",
            n_results=3
        )
        
        if results:
            return results[0].content
        return None
    
    async def get_condition_guidance(self, condition: str) -> Optional[str]:
        """Get guidance for managing a specific condition"""
        results = await self.search(
            f"{condition} management medication treatment",
            n_results=3,
            category_filter="conditions"
        )
        
        if results:
            return results[0].content
        return None
    
    def get_categories(self) -> List[str]:
        """Get all document categories"""
        categories = set()
        for doc in self.documents.values():
            if "category" in doc.metadata:
                categories.add(doc.metadata["category"])
        return sorted(list(categories))
    
    def get_document_count(self) -> int:
        """Get total number of documents"""
        return len(self.documents)


# Singleton instance
rag_system = RAGSystem()


async def search_knowledge(query: str, n_results: int = 5) -> List[SearchResult]:
    """Convenience function to search knowledge base"""
    return await rag_system.search(query, n_results)


async def get_medication_context(medication: str) -> str:
    """Convenience function to get medication context"""
    return await rag_system.get_context_for_query(f"{medication} medication")
