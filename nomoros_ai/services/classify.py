"""
Document classification service.

Provides deterministic, rule-based classification of legal documents.
Used for routing documents to the correct extraction and risk pipeline.

Design principles:
- NO LLM or ML used - purely deterministic rules
- Case-insensitive matching
- Returns UNKNOWN if ambiguous (multiple types match)
- All decisions are explainable via the reason field

Supported document types:
- TITLE_REGISTER: HM Land Registry Title Registers
- TA6: Property Information Forms (seller's questionnaire)
- SEARCH: Local Authority and other conveyancing searches
- LEASE: Leasehold documents
- UNKNOWN: Unrecognized or ambiguous documents
"""

from typing import Literal, get_args
from nomoros_ai.models.classification import DocumentClassification

# Valid document types - must match the Literal in DocumentClassification
DocumentType = Literal["TITLE_REGISTER", "TA6", "SEARCH", "LEASE", "COMPLIANCE_AML_ID", "COMPLIANCE_SOF", "UNKNOWN"]

# Classification rules: each document type has a list of indicator phrases
# If ANY phrase matches (case-insensitive), the document type is a candidate

CLASSIFICATION_RULES = {
    "TITLE_REGISTER": [
        "official copy of the register",
        "property register",
        "charges register",
        "hm land registry",
    ],
    "TA6": [
        "ta6",
        "property information form",
        "boundaries",
        "disputes and complaints",
    ],
    "SEARCH": [
        "local authority search",
        "con29",
        "llc1",
        "planning permissions",
    ],
    "LEASE": [
        "term of years",
        "landlord",
        "tenant",
        "ground rent",
    ],
    "COMPLIANCE_AML_ID": [
        "thirdfort",
        "credas",
        "pep screening",
        "sanctions screening",
        "aml check",
    ],
    "COMPLIANCE_SOF": [
        "source of funds",
        "source of wealth",
        "bank statement",
        "gift letter",
    ],
}

# Subtype classification for SEARCH documents
# Determines which extraction pipeline to use
SEARCH_SUBTYPE_RULES = {
    "Local Authority": [
        "local authority search",
        "con29",
        "llc1",
        "planning permission",
        "enforcement notice",
        "road adoption",
        "compulsory purchase",
        "building control",
    ],
    "Environmental": [
        "environmental search",
        "flood risk",
        "contaminated land",
        "radon",
        "ground stability",
        "homecheck",
        "landmark",
        "groundsure",
    ],
}


def classify_search_subtype(text: str) -> str:
    """
    Classify a SEARCH document into its subtype.
    
    Args:
        text: OCR-extracted text from the document
        
    Returns:
        Subtype string: "Local Authority", "Environmental", or "Unknown"
    """
    text_lower = text.lower()
    
    # Count matches for each subtype
    subtype_matches: dict[str, int] = {}
    
    for subtype, indicators in SEARCH_SUBTYPE_RULES.items():
        match_count = sum(1 for ind in indicators if ind.lower() in text_lower)
        if match_count > 0:
            subtype_matches[subtype] = match_count
    
    if not subtype_matches:
        return "Unknown"
    
    # Return the subtype with most matches
    return max(subtype_matches.keys(), key=lambda k: subtype_matches[k])


def classify_document(text: str) -> DocumentClassification:
    """
    Classify a document based on its extracted text.
    
    Uses deterministic rules to identify document type for routing
    to appropriate extraction and risk pipelines.
    
    Classification logic:
    1. Check text for indicator phrases for each document type
    2. If exactly one type matches, return that type
    3. If multiple types match, return UNKNOWN (ambiguous)
    4. If no types match, return UNKNOWN
    
    Args:
        text: OCR-extracted text from the document
        
    Returns:
        DocumentClassification with document_type and reason
    """
    text_lower = text.lower()
    
    # Track which document types match and which indicators triggered
    matches: dict[str, list[str]] = {}
    
    for doc_type, indicators in CLASSIFICATION_RULES.items():
        matched_indicators = []
        for indicator in indicators:
            if indicator.lower() in text_lower:
                matched_indicators.append(indicator)
        
        if matched_indicators:
            matches[doc_type] = matched_indicators
    
    # Decision logic: exactly one match = classified, otherwise UNKNOWN
    if len(matches) == 0:
        # No indicators matched any document type
        return DocumentClassification(
            document_type="UNKNOWN",
            reason="No recognized document indicators found in text"
        )
    
    elif len(matches) == 1:
        # Exactly one document type matched - unambiguous classification
        doc_type = list(matches.keys())[0]
        matched_indicators = matches[doc_type]
        
        # Build human-readable reason
        if doc_type == "TITLE_REGISTER":
            reason = f"Detected HM Land Registry headings: {', '.join(matched_indicators)}"
        elif doc_type == "TA6":
            reason = f"Detected TA6 Property Information Form indicators: {', '.join(matched_indicators)}"
        elif doc_type == "SEARCH":
            reason = f"Detected conveyancing search indicators: {', '.join(matched_indicators)}"
        elif doc_type == "LEASE":
            reason = f"Detected lease document indicators: {', '.join(matched_indicators)}"
        elif doc_type == "COMPLIANCE_AML_ID":
            reason = f"Detected AML/ID verification report indicators: {', '.join(matched_indicators)}"
        elif doc_type == "COMPLIANCE_SOF":
            reason = f"Detected Source of Funds evidence indicators: {', '.join(matched_indicators)}"
        else:
            reason = f"Matched indicators: {', '.join(matched_indicators)}"
        
        return DocumentClassification(
            document_type=doc_type,  # type: ignore[arg-type]
            reason=reason
        )
    
    else:
        # Multiple document types matched - ambiguous
        matched_types = list(matches.keys())
        indicator_summary = "; ".join(
            f"{t}: {', '.join(matches[t])}" for t in matched_types
        )
        return DocumentClassification(
            document_type="UNKNOWN",
            reason=f"Ambiguous classification - multiple document types matched: {indicator_summary}"
        )


# Legacy support: keep the old DocumentClassifier class for backward compatibility
# This wraps the new classify_document function

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    """
    Legacy result class for backward compatibility.
    
    Attributes:
        document_type: Identified document type
        confidence: Confidence score (0.0-1.0)
        matched_indicators: List of indicators that matched
    """
    document_type: str
    confidence: float
    matched_indicators: list[str]


class DocumentClassifier:
    """
    Legacy classifier class for backward compatibility.
    
    Wraps the new classify_document function to maintain
    existing API contracts.
    """
    
    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a document based on its extracted text.
        
        Args:
            text: OCR-extracted text from the document
            
        Returns:
            ClassificationResult with document type and confidence
        """
        result = classify_document(text)
        
        # Map new document types to legacy format
        type_mapping = {
            "TITLE_REGISTER": "Title Register",
            "TA6": "TA6 Form",
            "SEARCH": "Search",
            "LEASE": "Lease",
            "COMPLIANCE_AML_ID": "AML/ID Report",
            "COMPLIANCE_SOF": "Source of Funds",
            "UNKNOWN": "Unknown",
        }
        
        legacy_type = type_mapping.get(result.document_type, "Unknown")
        
        # Extract matched indicators from reason (approximate)
        matched = []
        for doc_type, indicators in CLASSIFICATION_RULES.items():
            if doc_type == result.document_type:
                text_lower = text.lower()
                matched = [i for i in indicators if i.lower() in text_lower]
                break
        
        # Confidence: 1.0 for definite match, 0.5 for ambiguous, 0.0 for unknown
        if result.document_type == "UNKNOWN":
            if "Ambiguous" in result.reason:
                confidence = 0.5
            else:
                confidence = 0.0
        else:
            confidence = 1.0
        
        return ClassificationResult(
            document_type=legacy_type,
            confidence=confidence,
            matched_indicators=matched
        )
    
    def is_title_register(self, text: str) -> bool:
        """
        Quick check if document is a Title Register.
        
        Args:
            text: Document text to analyze
            
        Returns:
            True if document is classified as Title Register
        """
        result = classify_document(text)
        return result.document_type == "TITLE_REGISTER"
