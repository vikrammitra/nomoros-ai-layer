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
    SYSTEM_PROMPT = """You are a legal document analysis assistant specializing in UK conveyancing.
Your task is to extract factual information from Local Authority Search documents.

STRICT RULES:
- Extract facts ONLY - do not assess severity or risk
- Do not make legal conclusions
- If information is unclear, return empty arrays
- Always return valid JSON
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
            logger.warning("Azure OpenAI not configured - falling back to basic extraction")
            return self._fallback_extraction(ocr_text)
        
        # Chunk the text
        chunks = self.chunker.chunk_text(ocr_text)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        if not chunks:
            return LocalAuthoritySearchExtraction()
        
        # Extract from each chunk
        chunk_extractions: list[LocalAuthorityChunkExtraction] = []
        source_sections: set[str] = set()
        
        for chunk in chunks:
            try:
                result = self._extract_from_chunk(chunk.content)
                chunk_extractions.append(result)
                
                if chunk.section_title:
                    source_sections.add(chunk.section_title)
                    
            except Exception as e:
                logger.error(f"Error extracting from chunk {chunk.chunk_index}: {e}")
                continue
        
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
        Basic regex-based extraction when Azure OpenAI is not available.
        
        This is a minimal fallback - Azure OpenAI provides much better results.
        """
        import re
        text = ocr_text.lower()
        
        extraction = LocalAuthoritySearchExtraction()
        
        # Basic pattern matching for key issues
        if any(phrase in text for phrase in ["enforcement notice", "stop notice", "breach of condition"]):
            extraction.enforcement_notices.append("Enforcement notice detected - requires review")
        
        if any(phrase in text for phrase in ["not adopted", "unadopted road", "private road"]):
            extraction.road_adoption_issues.append("Road adoption issue detected - requires review")
        
        if "compulsory purchase" in text:
            extraction.compulsory_purchase_orders.append("CPO reference detected - requires review")
        
        if any(phrase in text for phrase in ["further enquir", "recommend", "should be raised"]):
            extraction.further_action_required = True
        
        extraction.source_sections.append("Fallback Extraction")
        
        return extraction
