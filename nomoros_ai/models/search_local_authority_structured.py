"""
Structured output models for Local Authority Search results.

These models improve presentation and solicitor readability without
changing the underlying extraction or risk logic.
"""

from pydantic import BaseModel, Field
from typing import Any
from enum import Enum


class IssueLabel(str, Enum):
    """Neutral issue labels for categorising findings."""
    TRANSACTION_CONSTRAINT = "Transaction constraint"
    ONGOING_OBLIGATION = "Ongoing obligation"
    USE_RESTRICTION = "Use / alteration restriction"
    ENVIRONMENTAL_REGULATION = "Environmental regulation"
    MAINTENANCE_LIABILITY = "Maintenance liability"
    FINANCIAL_LIABILITY = "Financial liability"
    INFORMATIONAL = "Informational"


class LocalLandChargeEntry(BaseModel):
    """A single Local Land Charge entry with metadata."""
    description: str
    date_registered: str | None = None
    label: IssueLabel | None = None


class GroupedLocalLandCharges(BaseModel):
    """Local Land Charges grouped by type for easier scanning."""
    section_106_agreements: list[LocalLandChargeEntry] = Field(default_factory=list)
    tree_preservation_orders: list[LocalLandChargeEntry] = Field(default_factory=list)
    smoke_control_orders: list[LocalLandChargeEntry] = Field(default_factory=list)
    financial_charges: list[LocalLandChargeEntry] = Field(default_factory=list)
    other_charges: list[LocalLandChargeEntry] = Field(default_factory=list)


class PlanningRegisterEntry(BaseModel):
    """A structured Planning Register entry."""
    reference: str
    description: str
    decision_status: str | None = None
    decision_date: str | None = None
    is_historic: bool = True
    note: str | None = None


class RoadAdoptionFinding(BaseModel):
    """A Road Adoption finding with neutral implication."""
    road_name: str
    finding: str
    implication: str | None = None
    label: IssueLabel | None = None


class CILFinding(BaseModel):
    """A CIL finding distinguishing regime from liability."""
    finding_type: str  # "regime" or "liability"
    description: str
    clarification: str | None = None
    label: IssueLabel | None = None


class KeyIssuesSummary(BaseModel):
    """
    Lightweight summary of key issues identified.
    
    Rules:
    - Only references extracted findings
    - No severity scoring
    - No recommendations
    - No new interpretation
    """
    issues: list[str] = Field(default_factory=list)
    no_issues_found: list[str] = Field(default_factory=list)


class StructuredLocalAuthorityExtraction(BaseModel):
    """
    Structured extraction for solicitor-friendly presentation.
    
    Groups findings logically and adds neutral labels
    without changing underlying extraction or risk logic.
    """
    key_issues_summary: KeyIssuesSummary
    local_land_charges: GroupedLocalLandCharges
    planning_register: list[PlanningRegisterEntry] = Field(default_factory=list)
    road_adoption: list[RoadAdoptionFinding] = Field(default_factory=list)
    cil_findings: list[CILFinding] = Field(default_factory=list)
    enforcement_notices: list[str] = Field(default_factory=list)
    planning_breaches: list[str] = Field(default_factory=list)
    compulsory_purchase_orders: list[str] = Field(default_factory=list)
    further_action_required: bool | None = None
    further_action_details: list[str] = Field(default_factory=list)


class StructuredLocalAuthorityResponse(BaseModel):
    """
    Complete response for Local Authority Search with structured output.
    
    Provides both:
    - structured_extraction: Solicitor-friendly grouped presentation
    - risk_summary: Unchanged deterministic risk assessment
    - detailed_risks: Full risk objects with recommendations
    """
    document_type: str = "SEARCH"
    subtype: str = "Local Authority"
    structured_extraction: StructuredLocalAuthorityExtraction
    risk_summary: dict[str, Any]
    detailed_risks: list[dict[str, Any]] = Field(default_factory=list)
