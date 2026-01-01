"""
Document classification service for ingestion pipeline.

Provides deterministic, rule-based classification of legal documents
with confidence scoring. Returns document type and confidence score
for use in the ingestion response.

Design principles:
- NO LLM or ML used - purely deterministic rules
- Scoring-based confidence (matched markers / total markers)
- Returns UNKNOWN if confidence below threshold
- Pure function, testable without FastAPI imports
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ClassificationResult:
    """
    Result of document classification.
    
    Attributes:
        document_type: Identified document type
        confidence: Confidence score (0.0-1.0)
        method: Classification method used (e.g., "rules_v1")
    """
    document_type: str
    confidence: float
    method: str


CLASSIFICATION_MARKERS = {
    "TITLE_REGISTER": [
        "title number",
        "a: property register",
        "b: proprietorship register",
        "c: charges register",
        "this official copy is issued by the land registry",
        "hm land registry",
        "official copy of the register",
    ],
    "LOCAL_AUTHORITY_SEARCH": [
        "llc1",
        "con29",
        "local land charges register",
        "local authority search",
        "questions 1-",
        "planning and building regulations",
        "roads and public rights of way",
        "roadways, footways and footpaths",
    ],
    "ENVIRONMENTAL_SEARCH": [
        "environmental search",
        "flood risk",
        "contaminated land",
        "radon",
        "ground stability",
        "homecheck",
        "landmark",
        "groundsure",
    ],
    "TA6_PROPERTY_INFORMATION_FORM": [
        # Strong unique markers - Law Society TA6 form specific
        "ta6",
        "law society property information form",
        "property information form",
        "law society ta6",
        # Section headers unique to TA6
        "disputes and complaints",
        "alterations, planning and building control",
        "notices and proposals",
        "guarantees and warranties",
        "occupiers and employees",
        "services",
        # Structure markers
        "instructions to the seller",
        "instructions to the buyer",
        "seller's solicitor",
        "full names of the seller",
    ],
    "TR1_TRANSFER_DEED": [
        "tr1",
        "transfer of whole",
        "transferor",
        "transferee",
        "consideration",
        "title guarantee",
        "execution",
    ],
    "LEASE": [
        # More specific lease markers to avoid matching TA6 definitions
        "this lease is made",
        "hereby demises",
        "demised premises",
        "the landlord covenants",
        "the tenant covenants",
        "term of this lease",
        "reserved rent",
        "service charge",
        "yielding and paying",
    ],
    "COMPLIANCE_AML_ID": [
        # AML/ID verification provider reports - essential markers only
        "thirdfort",
        "credas",
        "pep screening",
        "sanctions screening",
        "aml check",
    ],
    "COMPLIANCE_SOF": [
        # Source of Funds evidence - essential markers only
        "source of funds",
        "source of wealth",
        "bank statement",
        "gift letter",
    ],
}

CONFIDENCE_THRESHOLD = 0.35


def classify_document(text: str) -> Tuple[str, float, str]:
    """
    Classify a document based on its extracted text.
    
    Uses deterministic rules with scoring to identify document type.
    Confidence = matched markers / total markers for that type.
    
    Args:
        text: OCR-extracted text from the document
        
    Returns:
        Tuple of (document_type, confidence, method)
        - document_type: One of the supported types or "UNKNOWN"
        - confidence: Score between 0.0 and 1.0
        - method: Classification method identifier ("rules_v1")
    """
    text_lower = text.lower()
    
    scores: dict[str, float] = {}
    
    for doc_type, markers in CLASSIFICATION_MARKERS.items():
        matched_count = sum(1 for marker in markers if marker.lower() in text_lower)
        total_markers = len(markers)
        
        if matched_count > 0:
            score = matched_count / total_markers
            scores[doc_type] = min(1.0, score)
    
    if not scores:
        return ("UNKNOWN", 0.0, "rules_v1")
    
    best_type = max(scores.keys(), key=lambda k: scores[k])
    best_score = scores[best_type]
    
    if best_score < CONFIDENCE_THRESHOLD:
        return ("UNKNOWN", best_score, "rules_v1")
    
    return (best_type, best_score, "rules_v1")


def get_classification_result(text: str) -> ClassificationResult:
    """
    Classify a document and return a structured result.
    
    Convenience wrapper around classify_document that returns
    a ClassificationResult dataclass.
    
    Args:
        text: OCR-extracted text from the document
        
    Returns:
        ClassificationResult with document_type, confidence, and method
    """
    doc_type, confidence, method = classify_document(text)
    return ClassificationResult(
        document_type=doc_type,
        confidence=confidence,
        method=method
    )
