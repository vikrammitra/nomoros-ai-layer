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

    # User prompt template for extraction - designed for stable, consistent extraction
    USER_PROMPT = """Extract the following from this Local Authority Search text. Be thorough and consistent.

1. local_land_charges - LOCAL LAND CHARGE REGISTER entries:
   - Section 106 / S106 planning agreements (include dates, parties)
   - Smoke control orders (Clean Air Act)
   - Tree preservation orders (TPO)
   - Financial charges, listed building designations
   
2. planning_register_entries - PLANNING REGISTER entries:
   - Applications: granted (PG/C), refused, pending, withdrawn
   - Include: reference numbers (e.g. 98/43306/FUL), dates, descriptions
   
3. enforcement_notices - ENFORCEMENT matters:
   - Enforcement notices, stop notices, breach of condition notices
   - Include dates and what they relate to
   
4. planning_breaches - PLANNING BREACHES:
   - Breach of planning conditions
   - Contravention of building regulations
   
5. road_adoption_issues - ROAD/HIGHWAY status:
   - Roads NOT adopted / unadopted / private roads
   - Roads not maintainable at public expense
   - Look for answers to Q2.1 about highways
   
6. compulsory_purchase_orders - CPO:
   - Any compulsory purchase order affecting the property
   
7. cil_liability - COMMUNITY INFRASTRUCTURE LEVY (CIL):
   - CIL charging schedule references
   - CIL liability notices or amounts
   - CIL commencement dates
   
8. further_action_required - Boolean: true if document recommends further enquiries

9. further_action_details - Specific recommendations for further action

Return valid JSON. Use empty arrays [] if nothing found for a category.
{
  "local_land_charges": ["Section 106 agreement dated 21/09/1998 between L B of Sutton and Linden Homes"],
  "planning_register_entries": ["98/43306/FUL - Erection of 43 flats - PG/C 21/09/1998"],
  "enforcement_notices": [],
  "planning_breaches": [],
  "road_adoption_issues": ["OSPREY CLOSE - not maintainable at public expense"],
  "compulsory_purchase_orders": [],
  "cil_liability": ["Sutton CIL commenced 1 April 2014"],
  "further_action_required": false,
  "further_action_details": []
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
            local_land_charges=result.get("local_land_charges", []),
            planning_register_entries=result.get("planning_register_entries", []),
            enforcement_notices=result.get("enforcement_notices", []),
            planning_breaches=result.get("planning_breaches", []),
            road_adoption_issues=result.get("road_adoption_issues", []),
            compulsory_purchase_orders=result.get("compulsory_purchase_orders", []),
            cil_liability=result.get("cil_liability", []),
            further_action_required=result.get("further_action_required"),
            further_action_details=result.get("further_action_details", [])
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
        local_land_charges: set[str] = set()
        planning_register_entries: set[str] = set()
        enforcement_notices: set[str] = set()
        planning_breaches: set[str] = set()
        road_adoption_issues: set[str] = set()
        compulsory_purchase_orders: set[str] = set()
        cil_liability: set[str] = set()
        further_action_required: bool | None = None
        further_action_details: set[str] = set()
        
        for ext in extractions:
            local_land_charges.update(ext.local_land_charges)
            planning_register_entries.update(ext.planning_register_entries)
            enforcement_notices.update(ext.enforcement_notices)
            planning_breaches.update(ext.planning_breaches)
            road_adoption_issues.update(ext.road_adoption_issues)
            compulsory_purchase_orders.update(ext.compulsory_purchase_orders)
            cil_liability.update(ext.cil_liability)
            further_action_details.update(ext.further_action_details)
            
            # Further action: True if any chunk says True
            if ext.further_action_required is True:
                further_action_required = True
            elif ext.further_action_required is False and further_action_required is None:
                further_action_required = False
        
        # Post-process: Check source_sections for key entries that might
        # have been miscategorized as section headings
        for section in source_sections:
            section_lower = section.lower()
            # Section 106 agreements
            if "section 106" in section_lower or "planning agreement" in section_lower:
                if section not in local_land_charges:
                    local_land_charges.add(section)
            # CIL references
            if "cil" in section_lower or "community infrastructure levy" in section_lower:
                if section not in cil_liability:
                    cil_liability.add(section)
        
        return LocalAuthoritySearchExtraction(
            local_land_charges=sorted(list(local_land_charges)),
            planning_register_entries=sorted(list(planning_register_entries)),
            enforcement_notices=sorted(list(enforcement_notices)),
            planning_breaches=sorted(list(planning_breaches)),
            road_adoption_issues=sorted(list(road_adoption_issues)),
            compulsory_purchase_orders=sorted(list(compulsory_purchase_orders)),
            cil_liability=sorted(list(cil_liability)),
            further_action_required=further_action_required,
            further_action_details=sorted(list(further_action_details)),
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
        
        local_land_charges = []
        planning_register_entries = []
        enforcement_notices = []
        planning_breaches = []
        road_adoption_issues = []
        compulsory_purchase_orders = []
        cil_liability = []
        further_action_required = None
        further_action_details = []
        source_sections = ["Fallback Extraction"]
        
        # Extract Local Land Charges
        llc_patterns = [
            r"section 106[^\n]*",
            r"s106[^\n]*agreement[^\n]*",
            r"planning agreement[^\n]*",
            r"smoke control[^\n]*order[^\n]*",
            r"clean air act[^\n]*",
            r"tree preservation[^\n]*order[^\n]*",
            r"tpo[^\n]*",
        ]
        for pattern in llc_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip() and len(match) > 15:
                    local_land_charges.append(match.strip().capitalize())
        
        # Extract planning register entries
        # Look for patterns like "planning permission granted/refused YYYY/NNNNN" or "PG/C"
        pp_patterns = [
            r"\d{2,4}/\d+(?:/\w+)?[^\n]*(?:pg/c|granted|approved|refused|pending)[^\n]*",
            r"(?:pg/c|granted|refused|pending)\s+\d{2}/\d{2}/\d{4}[^\n]*",
            r"planning (?:permission|consent|application)[^\n]*\d{4}/\d+[^\n]*",
        ]
        for pattern in pp_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip() and len(match) > 15:
                    planning_register_entries.append(match.strip().upper())
        
        # Extract CIL references
        cil_patterns = [
            r"cil[^\n]*commenced[^\n]*",
            r"community infrastructure levy[^\n]*",
            r"cil[^\n]*charging[^\n]*schedule[^\n]*",
            r"cil[^\n]*liability[^\n]*",
        ]
        for pattern in cil_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match.strip() and len(match) > 10:
                    cil_liability.append(match.strip().capitalize())
        
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
        
        # Check for further action details
        if "further enquir" in text:
            further_action_details.append("Further enquiries recommended")
        if "should be raised" in text:
            further_action_details.append("Questions should be raised with vendor")
        
        # Deduplicate and clean up
        planning_register_entries = list(set(planning_register_entries))
        enforcement_notices = list(set(enforcement_notices))
        planning_breaches = list(set(planning_breaches))
        cil_liability = list(set(cil_liability))
        
        # Deduplicate road issues more aggressively - keep longest unique
        unique_roads = []
        for issue in sorted(road_adoption_issues, key=len, reverse=True):
            is_duplicate = False
            for existing in unique_roads:
                if issue.lower() in existing.lower() or existing.lower() in issue.lower():
                    is_duplicate = True
                    break
            if not is_duplicate and len(issue) > 15:
                unique_roads.append(issue)
        road_adoption_issues = unique_roads
        
        # Deduplicate local land charges
        local_land_charges = list(set(local_land_charges))
        
        return LocalAuthoritySearchExtraction(
            local_land_charges=local_land_charges,
            planning_register_entries=planning_register_entries,
            enforcement_notices=enforcement_notices,
            planning_breaches=planning_breaches,
            road_adoption_issues=road_adoption_issues,
            compulsory_purchase_orders=compulsory_purchase_orders,
            cil_liability=cil_liability,
            further_action_required=further_action_required,
            further_action_details=further_action_details,
            source_sections=source_sections
        )
