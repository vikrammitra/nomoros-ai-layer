"""
Response model for Local Authority Search analysis.
"""

from pydantic import BaseModel, Field
from typing import Any

from nomoros_ai.models.search_local_authority import LocalAuthoritySearchExtraction
from nomoros_ai.models.title import RiskSummary


class LocalAuthoritySearchResponse(BaseModel):
    """
    Complete response for Local Authority Search risk analysis endpoint.
    
    Attributes:
        document_type: Always "SEARCH" for search documents
        subtype: "Local Authority" for this pipeline
        extraction: Structured data extracted from the search
        risk_summary: Summary of identified risks
        detailed_risks: Full list of risk objects with recommendations
    """
    document_type: str = "SEARCH"
    subtype: str = "Local Authority"
    extraction: LocalAuthoritySearchExtraction
    risk_summary: RiskSummary
    detailed_risks: list[dict[str, Any]] = Field(default_factory=list)
