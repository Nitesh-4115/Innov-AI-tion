"""
Knowledge Base Module
Data loaders and stores for medication and clinical knowledge
"""

from .vector_store import (
    Document,
    SearchResult,
    VectorStore,
    KnowledgeBaseStore,
    vector_store,
    knowledge_base
)

from .clinical_guidelines import (
    ClinicalGuideline,
    ClinicalGuidelinesService,
    clinical_guidelines_service,
    CLINICAL_GUIDELINES,
    ADHERENCE_BARRIER_TIPS
)

from .rxnorm_client import (
    DrugConcept,
    DrugInteraction as RxNormDrugInteraction,
    DrugProperty,
    RxNormClient,
    SyncRxNormClient,
    rxnorm_client,
    sync_rxnorm_client
)

from .drugbank_loader import (
    DrugInfo,
    DrugInteraction as DrugBankInteraction,
    DrugBankLoader,
    drugbank_loader,
    COMMON_DRUGS
)

from .sider_loader import (
    SideEffect,
    DrugSideEffects,
    SIDERLoader,
    sider_loader,
    COMMON_DRUG_SIDE_EFFECTS,
    SYMPTOM_SIDE_EFFECT_MAP
)


__all__ = [
    # Vector Store
    "Document",
    "SearchResult",
    "VectorStore",
    "KnowledgeBaseStore",
    "vector_store",
    "knowledge_base",
    
    # Clinical Guidelines
    "ClinicalGuideline",
    "ClinicalGuidelinesService",
    "clinical_guidelines_service",
    "CLINICAL_GUIDELINES",
    "ADHERENCE_BARRIER_TIPS",
    
    # RxNorm
    "DrugConcept",
    "RxNormDrugInteraction",
    "DrugProperty",
    "RxNormClient",
    "SyncRxNormClient",
    "rxnorm_client",
    "sync_rxnorm_client",
    
    # DrugBank
    "DrugInfo",
    "DrugBankInteraction",
    "DrugBankLoader",
    "drugbank_loader",
    "COMMON_DRUGS",
    
    # SIDER
    "SideEffect",
    "DrugSideEffects",
    "SIDERLoader",
    "sider_loader",
    "COMMON_DRUG_SIDE_EFFECTS",
    "SYMPTOM_SIDE_EFFECT_MAP"
]
