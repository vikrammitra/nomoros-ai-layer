"""
Document classification model.

Pydantic model for deterministic document classification results.
Used for routing documents to the correct extraction and risk pipeline.

Design notes:
- Supports standard conveyancing document types
- UNKNOWN is returned for ambiguous or unrecognized documents
- reason field provides human-readable explanation for audit trail
"""

from pydantic import BaseModel
from typing import Literal


class DocumentClassification(BaseModel):
    """
    Result of document classification.
    
    This model is used to route documents to appropriate extraction
    and risk analysis pipelines. Classification is deterministic
    and rule-based for legal defensibility.
    
    Attributes:
        document_type: Identified document type for routing
        reason: Human-readable explanation of classification decision
    """
    document_type: Literal[
        "TITLE_REGISTER",
        "TA6",
        "SEARCH",
        "LEASE",
        "COMPLIANCE_AML_ID",
        "COMPLIANCE_SOF",
        "UNKNOWN"
    ]
    reason: str
