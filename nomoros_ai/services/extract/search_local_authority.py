"""
Local Authority Search extraction service.

Uses Azure OpenAI for assistive extraction of planning and enforcement
information from Local Authority Search documents (CON29).

IMPORTANT:
- LLM is used for EXTRACTION only
- No legal conclusions are made by the LLM
- No severity assignments are made by the LLM
- All risk decisions are made in the deterministic rules layer
"""

import logging
from typing import Any

from nomoros_ai.models.search_local_authority import (
    LocalAuthoritySearchExtraction,
    LocalAuthorityChunkExtraction,
)
from nomoros_ai.services.chunking.text_chunker import TextChunker
from nomoros_ai.services.llm.azure_openai_client import AzureOpenAIClient

logger = logging.getLogger(__name__)


class LocalAuthoritySearchExtractor:
    """
    Extracts structured data from Local Authority Search documents.
    
    Workflow:
    1. Chunk OCR text into LLM-safe segments
    2. For each chunk, call Azure OpenAI with strict extraction prompt
    3. Aggregate and deduplicate findings across chunks
    4. Return structured LocalAuthoritySearchExtraction
    """
    
    # System prompt: Define LLM role and constraints
    # Note: Must mention "JSON" explicitly for Azure OpenAI json_object mode
    SYSTEM_PROMPT = """You are a legal document analysis assistant that outputs JSON.
You specialize in UK conveyancing and extract factual information from Local Authority Search documents.

STRICT RULES:
- Extract facts ONLY - do not assess severity or risk
- Do not make legal conclusions
- If information is unclear, return empty arrays
- Always respond with valid JSON only
- Prefer false negatives over false positives"""

    # User prompt template for extraction
    USER_PROMPT = """From the following Local Authority Search text, extract:

1. planning_permissions - Any planning permissions (approved, pending, refused, withdrawn)
   Include: application references, dates, descriptions
   
2. enforcement_notices - Any enforcement notices or stop notices
   Include: dates, descriptions, what they relate to
   
3. planning_breaches - Any breaches of planning conditions
   Include: what conditions were breached
   
4. road_adoption_issues - Any road adoption status issues
   Look for: "not adopted", "private road", "unadopted", "adoption scheme"
   
5. compulsory_purchase_orders - Any CPO affecting the property
   Include: dates, acquiring authority, purpose
   
6. further_action_required - Boolean, true if the document recommends further enquiries

Return valid JSON with these exact keys. Use empty arrays [] if nothing found.
Example format:
{
  "planning_permissions": ["Permission granted 2020/12345 for rear extension"],
  "enforcement_notices": [],
  "planning_breaches": [],
  "road_adoption_issues": ["Road serving property is not adopted"],
  "compulsory_purchase_orders": [],
  "further_action_required": false
}"""

    def __init__(self, openai_client: AzureOpenAIClient | None = None):
        """
        Initialize extractor with optional OpenAI client.
        
        Args:
            openai_client: Azure OpenAI client instance. If None, creates new one.
        """
        self.chunker = TextChunker()
        self.openai_client = openai_client or AzureOpenAIClient()
    
    def extract(self, ocr_text: str) -> LocalAuthoritySearchExtraction:
        """
        Extract Local Authority Search data from OCR text.
        
        Args:
            ocr_text: Full OCR text from the document
            
        Returns:
            LocalAuthoritySearchExtraction with aggregated findings
        """
        if not ocr_text or not ocr_text.strip():
            logger.warning("Empty OCR text provided")
            return LocalAuthoritySearchExtraction()
        
        # Check if Azure OpenAI is configured
        if not self.openai_client.is_configured:
            logger.warning("Azure OpenAI not configured - falling back to regex extraction")
            return self._fallback_extraction(ocr_text)
        
        # Chunk the text
        chunks = self.chunker.chunk_text(ocr_text)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        if not chunks:
            return LocalAuthoritySearchExtraction()
        
        # Extract from each chunk
        chunk_extractions: list[LocalAuthorityChunkExtraction] = []
        source_sections: set[str] = set()
        failed_chunks = 0
        
        for chunk in chunks:
            try:
                result = self._extract_from_chunk(chunk.content)
                chunk_extractions.append(result)
                
                if chunk.section_title:
                    source_sections.add(chunk.section_title)
                    
            except Exception as e:
                logger.error(f"Error extracting from chunk {chunk.chunk_index}: {e}")
                failed_chunks += 1
                continue
        
        # If all chunks failed, fall back to regex extraction
        if failed_chunks == len(chunks):
            logger.warning("All Azure OpenAI extractions failed - falling back to regex extraction")
            return self._fallback_extraction(ocr_text)
        
        # Aggregate and deduplicate findings
        return self._aggregate_extractions(chunk_extractions, list(source_sections))
    
    def _extract_from_chunk(self, chunk_text: str) -> LocalAuthorityChunkExtraction:
        """
        Extract data from a single text chunk using Azure OpenAI.
        """
        result = self.openai_client.extract_structured(
            text_chunk=chunk_text,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=self.USER_PROMPT
        )
        
        # Parse into Pydantic model with validation
        return LocalAuthorityChunkExtraction(
            planning_permissions=result.get("planning_permissions", []),
            enforcement_notices=result.get("enforcement_notices", []),
            planning_breaches=result.get("planning_breaches", []),
            road_adoption_issues=result.get("road_adoption_issues", []),
            compulsory_purchase_orders=result.get("compulsory_purchase_orders", []),
            further_action_required=result.get("further_action_required")
        )
    
    def _aggregate_extractions(
        self,
        extractions: list[LocalAuthorityChunkExtraction],
        source_sections: list[str]
    ) -> LocalAuthoritySearchExtraction:
        """
        Aggregate and deduplicate findings from multiple chunks.
        """
        # Use sets for deduplication
        planning_permissions: set[str] = set()
        enforcement_notices: set[str] = set()
        planning_breaches: set[str] = set()
        road_adoption_issues: set[str] = set()
        compulsory_purchase_orders: set[str] = set()
        further_action_required: bool | None = None
        
        for ext in extractions:
            planning_permissions.update(ext.planning_permissions)
            enforcement_notices.update(ext.enforcement_notices)
            planning_breaches.update(ext.planning_breaches)
            road_adoption_issues.update(ext.road_adoption_issues)
            compulsory_purchase_orders.update(ext.compulsory_purchase_orders)
            
            # Further action: True if any chunk says True
            if ext.further_action_required is True:
                further_action_required = True
            elif ext.further_action_required is False and further_action_required is None:
                further_action_required = False
        
        return LocalAuthoritySearchExtraction(
            planning_permissions=sorted(list(planning_permissions)),
            enforcement_notices=sorted(list(enforcement_notices)),
            planning_breaches=sorted(list(planning_breaches)),
            road_adoption_issues=sorted(list(road_adoption_issues)),
            compulsory_purchase_orders=sorted(list(compulsory_purchase_orders)),
            further_action_required=further_action_required,
            source_sections=sorted(source_sections)
        )
    
    def _fallback_extraction(self, ocr_text: str) -> LocalAuthoritySearchExtraction:
        """
        Regex-based extraction when Azure OpenAI is not available.
        
        This provides basic extraction capability as a fallback.
        Azure OpenAI provides more comprehensive results when configured.
        """
        import re
        text = ocr_text.lower()
        
        planning_permissions = []
        enforcement_notices = []
        planning_breaches = []
        road_adoption_issues = []
        compulsory_purchase_orders = []
        further_action_required = None
        source_sections = ["Fallback Extraction"]
        
        # Extract planning permissions
        # Look for patterns like "planning permission granted/refused YYYY/NNNNN"
        pp_patterns = [
            r"planning (?:permission|consent) (?:granted|approved|refused|pending)[^\n]*",
            r"(?:application|ref(?:erence)?)[:\s]*\d{4}/\d+[^\n]*",
        ]
        for pattern in pp_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip() and len(match) > 10:
                    planning_permissions.append(match.strip().capitalize())
        
        # Extract enforcement notices
        # Must contain more than just "Enforcement Notice" heading
        enforcement_patterns = [
            r"enforcement notice dated[^\n]*",
            r"enforcement notice[^\n]{10,}",  # Must have substantial content after
            r"stop notice dated[^\n]*",
            r"breach of (?:planning )?condition[^\n]*",
        ]
        for pattern in enforcement_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                match = match.strip()
                # Skip section headings
                if match and len(match) > 20 and match.lower() not in ["enforcement notices", "enforcement notice"]:
                    enforcement_notices.append(match.capitalize())
        
        # Check for planning breaches
        if "breach" in text and ("condition" in text or "planning" in text):
            breach_match = re.search(r"breach[^\n]{0,100}", text)
            if breach_match:
                planning_breaches.append(breach_match.group().strip().capitalize())
        
        # Extract road adoption issues
        road_patterns = [
            r"(?:road|highway)[^\.]*(?:not adopted|unadopted|private)[^\.]*",
            r"private road[^\n]*",
            r"not adopted[^\n]*",
        ]
        for pattern in road_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip() and len(match) > 10:
                    road_adoption_issues.append(match.strip().capitalize())
        
        # Check for compulsory purchase orders
        # Look for actual CPO references, not just section headings
        cpo_patterns = [
            r"compulsory purchase order[^\n]{10,}",  # Must have content after
            r"cpo[^\n]*affecting[^\n]*",
        ]
        for pattern in cpo_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                match = match.strip()
                # Skip headings and "None" statements
                if match and len(match) > 25:
                    if "none" not in match.lower() and match.lower() not in ["compulsory purchase orders", "compulsory purchase order"]:
                        compulsory_purchase_orders.append(match.capitalize())
        
        # Check for further action required
        further_action_patterns = [
            "further enquir",
            "recommend",
            "should be raised",
            "additional information required",
            "further investigation",
        ]
        if any(phrase in text for phrase in further_action_patterns):
            further_action_required = True
        
        # Deduplicate and clean up
        planning_permissions = list(set(planning_permissions))
        enforcement_notices = list(set(enforcement_notices))
        planning_breaches = list(set(planning_breaches))
        
        # Deduplicate road issues more aggressively - keep longest unique
        unique_roads = []
        for issue in sorted(road_adoption_issues, key=len, reverse=True):
            # Only add if not a substring of existing
            is_duplicate = False
            for existing in unique_roads:
                if issue.lower() in existing.lower() or existing.lower() in issue.lower():
                    is_duplicate = True
                    break
            if not is_duplicate and len(issue) > 15:
                unique_roads.append(issue)
        road_adoption_issues = unique_roads
        
        return LocalAuthoritySearchExtraction(
            planning_permissions=planning_permissions,
            enforcement_notices=enforcement_notices,
            planning_breaches=planning_breaches,
            road_adoption_issues=road_adoption_issues,
            compulsory_purchase_orders=compulsory_purchase_orders,
            further_action_required=further_action_required,
            source_sections=source_sections
        )
