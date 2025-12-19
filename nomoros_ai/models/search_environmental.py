"""
Environmental Search extraction models.

Pydantic models for structured extraction from UK Environmental Search
reports (Homecheck, Landmark, etc.) used in conveyancing transactions.

These reports cover:
- Flood risk assessment
- Contaminated land registers
- Historic industrial land use
- Mining and subsidence risk
- Ground stability concerns
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


class EnvironmentalSearchExtraction(BaseModel):
    """
    Structured extraction from an Environmental Search report.
    
    UK Environmental Searches typically include:
    - Section 1: Contamination Risk (Part 2A EPA 1990)
    - Section 2: Flood Risk (EA flood maps)
    - Section 3: Radon Risk (PHE data)
    - Section 4: Ground Stability (BGS data)
    - Section 5: Other factors (energy, infrastructure, etc.)
    
    Attributes:
        flood_risk: Overall flood risk level from the report
        contaminated_land: Whether property is on or near contaminated land
        historic_industrial_use: Whether historic industrial use is identified
        mining_or_subsidence: Whether mining/subsidence risk exists
        radon_risk: Whether property is in a radon affected area
        ground_stability_risk: Whether ground stability concerns identified
        further_action_required: Whether report recommends further investigation
        source_sections: List of report sections that were analyzed
    """
    flood_risk: Literal["None", "Low", "Medium", "High", "Unknown"] = Field(
        default="Unknown",
        description="Flood risk level from Section 2 of environmental report"
    )
    contaminated_land: Optional[bool] = Field(
        default=None,
        description="Whether contaminated land is identified within search radius"
    )
    historic_industrial_use: Optional[bool] = Field(
        default=None,
        description="Whether historic potentially contaminative activities identified"
    )
    mining_or_subsidence: Optional[bool] = Field(
        default=None,
        description="Whether mining or subsidence risk is identified"
    )
    radon_risk: Optional[bool] = Field(
        default=None,
        description="Whether property is in a radon affected area"
    )
    ground_stability_risk: Optional[bool] = Field(
        default=None,
        description="Whether natural or man-made ground stability risk exists"
    )
    further_action_required: Optional[bool] = Field(
        default=None,
        description="Whether report recommends further investigation or action"
    )
    source_sections: list[str] = Field(
        default_factory=list,
        description="Report sections that were successfully analyzed"
    )


class EnvironmentalRisk(BaseModel):
    """
    An individual environmental risk identified in the search report.
    
    Attributes:
        category: Risk category (always "Searches - Environmental")
        severity: Risk severity level
        description: Human-readable explanation for solicitors
        recommendation: Suggested action to address the risk
    """
    category: str = "Searches - Environmental"
    severity: Literal["High", "Medium", "Low"]
    description: str
    recommendation: Optional[str] = None


class EnvironmentalRiskSummary(BaseModel):
    """
    Summary of environmental risks identified in a search report.
    
    Attributes:
        category: Primary risk category
        severity: Highest severity among all risks
        severity_breakdown: Count of risks by severity level
        risk_count: Total number of risks identified
        risks: List of human-readable risk descriptions
    """
    category: str = "Searches - Environmental"
    severity: Literal["High", "Medium", "Low", "None"]
    severity_breakdown: dict[str, int] = Field(default_factory=lambda: {"high": 0, "medium": 0, "low": 0})
    risk_count: int = 0
    risks: list[str] = Field(default_factory=list)


class EnvironmentalSearchResponse(BaseModel):
    """
    Complete response for environmental search analysis endpoint.
    
    Attributes:
        document_type: Always "SEARCH" for search documents
        subtype: "Environmental" for environmental search reports
        extraction: Structured data extracted from the report
        risk_summary: Summary of identified risks
        detailed_risks: Full list of risk objects with recommendations
    """
    document_type: str = "SEARCH"
    subtype: str = "Environmental"
    extraction: EnvironmentalSearchExtraction
    risk_summary: EnvironmentalRiskSummary
    detailed_risks: list[EnvironmentalRisk] = Field(default_factory=list)
