"""
RxNorm API Client
Client for the NLM RxNorm REST API for drug information lookups
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class DrugConcept:
    """RxNorm drug concept"""
    rxcui: str
    name: str
    tty: str  # Term type (SBD, SCD, GPCK, etc.)
    synonym: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rxcui": self.rxcui,
            "name": self.name,
            "tty": self.tty,
            "synonym": self.synonym
        }


@dataclass
class DrugInteraction:
    """Drug-drug interaction"""
    drug1_name: str
    drug1_rxcui: str
    drug2_name: str
    drug2_rxcui: str
    description: str
    severity: str
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug1_name": self.drug1_name,
            "drug1_rxcui": self.drug1_rxcui,
            "drug2_name": self.drug2_name,
            "drug2_rxcui": self.drug2_rxcui,
            "description": self.description,
            "severity": self.severity,
            "source": self.source
        }


@dataclass
class DrugProperty:
    """Drug property from RxNorm"""
    prop_name: str
    prop_value: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.prop_name,
            "value": self.prop_value
        }


class RxNormCache:
    """Simple in-memory cache for RxNorm API responses"""
    
    def __init__(self, ttl_hours: int = 24):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(hours=ttl_hours)
    
    def _get_key(self, method: str, params: Dict[str, Any]) -> str:
        """Generate cache key"""
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{method}:{param_str}".encode()).hexdigest()
    
    def get(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached response"""
        key = self._get_key(method, params)
        
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < self._ttl:
                return entry["data"]
            else:
                del self._cache[key]
        
        return None
    
    def set(self, method: str, params: Dict[str, Any], data: Any):
        """Cache response"""
        key = self._get_key(method, params)
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
    def clear(self):
        """Clear cache"""
        self._cache.clear()


class RxNormClient:
    """
    Client for RxNorm REST API
    
    API Documentation: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.RXNORM_API_URL).rstrip('/')
        self._cache = RxNormCache()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for RxNorm API. Install with: pip install httpx")
        
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={"Accept": "application/json"}
            )
        
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request with caching"""
        cache_key_params = params or {}
        
        # Check cache
        cached = self._cache.get(endpoint, cache_key_params)
        if cached is not None:
            return cached
        
        try:
            client = await self._get_client()
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            
            data = response.json()
            self._cache.set(endpoint, cache_key_params, data)
            
            return data
            
        except httpx.HTTPError as e:
            logger.error(f"RxNorm API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling RxNorm: {e}")
            return None
    
    async def search_drugs(
        self,
        name: str,
        search_type: int = 0
    ) -> List[DrugConcept]:
        """
        Search for drugs by name
        
        Args:
            name: Drug name to search
            search_type: 0=exact, 1=normalized, 2=best match
            
        Returns:
            List of matching drug concepts
        """
        data = await self._request(
            "/drugs.json",
            params={"name": name, "searchType": search_type}
        )
        
        concepts = []
        
        if data and "drugGroup" in data:
            drug_group = data["drugGroup"]
            
            if "conceptGroup" in drug_group:
                for group in drug_group["conceptGroup"]:
                    if "conceptProperties" in group:
                        for prop in group["conceptProperties"]:
                            concepts.append(DrugConcept(
                                rxcui=prop.get("rxcui", ""),
                                name=prop.get("name", ""),
                                tty=prop.get("tty", ""),
                                synonym=prop.get("synonym")
                            ))
        
        return concepts
    
    async def get_rxcui(self, drug_name: str) -> Optional[str]:
        """
        Get RxCUI for a drug name
        
        Args:
            drug_name: Drug name
            
        Returns:
            RxCUI or None if not found
        """
        data = await self._request(
            "/rxcui.json",
            params={"name": drug_name, "search": 2}  # Approximate match
        )
        
        if data and "idGroup" in data:
            id_group = data["idGroup"]
            if "rxnormId" in id_group and id_group["rxnormId"]:
                return id_group["rxnormId"][0]
        
        return None
    
    async def get_drug_properties(
        self,
        rxcui: str
    ) -> List[DrugProperty]:
        """
        Get drug properties by RxCUI
        
        Args:
            rxcui: RxNorm concept identifier
            
        Returns:
            List of drug properties
        """
        data = await self._request(f"/rxcui/{rxcui}/properties.json")
        
        properties = []
        
        if data and "properties" in data:
            props = data["properties"]
            for key, value in props.items():
                if value:
                    properties.append(DrugProperty(
                        prop_name=key,
                        prop_value=str(value)
                    ))
        
        return properties
    
    async def get_drug_info(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive drug information
        
        Args:
            drug_name: Drug name
            
        Returns:
            Drug information dictionary
        """
        rxcui = await self.get_rxcui(drug_name)
        
        if not rxcui:
            # Try searching
            concepts = await self.search_drugs(drug_name, search_type=2)
            if concepts:
                rxcui = concepts[0].rxcui
        
        if not rxcui:
            return None
        
        properties = await self.get_drug_properties(rxcui)
        
        return {
            "rxcui": rxcui,
            "name": drug_name,
            "properties": [p.to_dict() for p in properties]
        }
    
    async def get_related_drugs(
        self,
        rxcui: str,
        relation_types: Optional[List[str]] = None
    ) -> List[DrugConcept]:
        """
        Get related drug concepts
        
        Args:
            rxcui: RxNorm concept identifier
            relation_types: Specific relation types to retrieve
            
        Returns:
            List of related drug concepts
        """
        params = {}
        if relation_types:
            params["rela"] = "+".join(relation_types)
        
        data = await self._request(
            f"/rxcui/{rxcui}/related.json",
            params=params if params else None
        )
        
        concepts = []
        
        if data and "relatedGroup" in data:
            related = data["relatedGroup"]
            if "conceptGroup" in related:
                for group in related["conceptGroup"]:
                    if "conceptProperties" in group:
                        for prop in group["conceptProperties"]:
                            concepts.append(DrugConcept(
                                rxcui=prop.get("rxcui", ""),
                                name=prop.get("name", ""),
                                tty=prop.get("tty", ""),
                                synonym=prop.get("synonym")
                            ))
        
        return concepts
    
    async def get_drug_interactions(
        self,
        rxcui: str
    ) -> List[DrugInteraction]:
        """
        Get drug interactions for a single drug
        
        Args:
            rxcui: RxNorm concept identifier
            
        Returns:
            List of drug interactions
        """
        data = await self._request(f"/interaction/interaction.json", params={"rxcui": rxcui})
        
        interactions = []
        
        if data and "interactionTypeGroup" in data:
            for type_group in data["interactionTypeGroup"]:
                source_name = type_group.get("sourceName", "Unknown")
                
                if "interactionType" in type_group:
                    for int_type in type_group["interactionType"]:
                        if "interactionPair" in int_type:
                            for pair in int_type["interactionPair"]:
                                concepts = pair.get("interactionConcept", [])
                                
                                if len(concepts) >= 2:
                                    interactions.append(DrugInteraction(
                                        drug1_name=concepts[0].get("minConceptItem", {}).get("name", ""),
                                        drug1_rxcui=concepts[0].get("minConceptItem", {}).get("rxcui", ""),
                                        drug2_name=concepts[1].get("minConceptItem", {}).get("name", ""),
                                        drug2_rxcui=concepts[1].get("minConceptItem", {}).get("rxcui", ""),
                                        description=pair.get("description", ""),
                                        severity=pair.get("severity", "Unknown"),
                                        source=source_name
                                    ))
        
        return interactions
    
    async def check_interactions_between(
        self,
        rxcuis: List[str]
    ) -> List[DrugInteraction]:
        """
        Check interactions between multiple drugs
        
        Args:
            rxcuis: List of RxCUI identifiers
            
        Returns:
            List of drug interactions
        """
        if len(rxcuis) < 2:
            return []
        
        rxcui_str = "+".join(rxcuis)
        
        data = await self._request(
            "/interaction/list.json",
            params={"rxcuis": rxcui_str}
        )
        
        interactions = []
        
        if data and "fullInteractionTypeGroup" in data:
            for type_group in data["fullInteractionTypeGroup"]:
                source_name = type_group.get("sourceName", "Unknown")
                
                if "fullInteractionType" in type_group:
                    for int_type in type_group["fullInteractionType"]:
                        if "interactionPair" in int_type:
                            for pair in int_type["interactionPair"]:
                                concepts = pair.get("interactionConcept", [])
                                
                                if len(concepts) >= 2:
                                    interactions.append(DrugInteraction(
                                        drug1_name=concepts[0].get("minConceptItem", {}).get("name", ""),
                                        drug1_rxcui=concepts[0].get("minConceptItem", {}).get("rxcui", ""),
                                        drug2_name=concepts[1].get("minConceptItem", {}).get("name", ""),
                                        drug2_rxcui=concepts[1].get("minConceptItem", {}).get("rxcui", ""),
                                        description=pair.get("description", ""),
                                        severity=pair.get("severity", "Unknown"),
                                        source=source_name
                                    ))
        
        return interactions
    
    async def get_ndc_codes(self, rxcui: str) -> List[str]:
        """
        Get NDC codes for a drug
        
        Args:
            rxcui: RxNorm concept identifier
            
        Returns:
            List of NDC codes
        """
        data = await self._request(f"/rxcui/{rxcui}/ndcs.json")
        
        if data and "ndcGroup" in data:
            ndc_list = data["ndcGroup"].get("ndcList", {})
            return ndc_list.get("ndc", [])
        
        return []
    
    async def get_drug_class(self, rxcui: str) -> List[Dict[str, str]]:
        """
        Get drug class information
        
        Args:
            rxcui: RxNorm concept identifier
            
        Returns:
            List of drug classes
        """
        data = await self._request(
            f"/rxclass/class/byRxcui.json",
            params={"rxcui": rxcui}
        )
        
        classes = []
        
        if data and "rxclassDrugInfoList" in data:
            drug_info_list = data["rxclassDrugInfoList"].get("rxclassDrugInfo", [])
            
            for info in drug_info_list:
                concept = info.get("rxclassMinConceptItem", {})
                classes.append({
                    "class_id": concept.get("classId", ""),
                    "class_name": concept.get("className", ""),
                    "class_type": concept.get("classType", "")
                })
        
        return classes
    
    async def spell_check(self, term: str) -> List[str]:
        """
        Get spelling suggestions for a drug name
        
        Args:
            term: Drug name to check
            
        Returns:
            List of spelling suggestions
        """
        data = await self._request("/spellingsuggestions.json", params={"name": term})
        
        if data and "suggestionGroup" in data:
            suggestion_list = data["suggestionGroup"].get("suggestionList", {})
            return suggestion_list.get("suggestion", [])
        
        return []
    
    async def get_approximate_matches(
        self,
        term: str,
        max_entries: int = 5
    ) -> List[DrugConcept]:
        """
        Get approximate matches for a drug name
        
        Args:
            term: Drug name to search
            max_entries: Maximum number of results
            
        Returns:
            List of matching drug concepts
        """
        data = await self._request(
            "/approximateTerm.json",
            params={"term": term, "maxEntries": max_entries}
        )
        
        concepts = []
        
        if data and "approximateGroup" in data:
            candidates = data["approximateGroup"].get("candidate", [])
            
            for candidate in candidates:
                concepts.append(DrugConcept(
                    rxcui=candidate.get("rxcui", ""),
                    name=candidate.get("name", ""),
                    tty=candidate.get("tty", ""),
                    synonym=None
                ))
        
        return concepts


# Synchronous wrapper for convenience
class SyncRxNormClient:
    """Synchronous wrapper for RxNormClient"""
    
    def __init__(self):
        self._async_client = RxNormClient()
    
    def _run(self, coro):
        """Run async coroutine synchronously"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    def search_drugs(self, name: str) -> List[DrugConcept]:
        return self._run(self._async_client.search_drugs(name))
    
    def get_rxcui(self, drug_name: str) -> Optional[str]:
        return self._run(self._async_client.get_rxcui(drug_name))
    
    def get_drug_info(self, drug_name: str) -> Optional[Dict[str, Any]]:
        return self._run(self._async_client.get_drug_info(drug_name))
    
    def get_drug_interactions(self, rxcui: str) -> List[DrugInteraction]:
        return self._run(self._async_client.get_drug_interactions(rxcui))
    
    def check_interactions_between(self, rxcuis: List[str]) -> List[DrugInteraction]:
        return self._run(self._async_client.check_interactions_between(rxcuis))
    
    def get_drug_class(self, rxcui: str) -> List[Dict[str, str]]:
        return self._run(self._async_client.get_drug_class(rxcui))


# Singleton instances
rxnorm_client = RxNormClient()
sync_rxnorm_client = SyncRxNormClient()
