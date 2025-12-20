"""
Pydantic models for Local Authority Search extraction.

Local Authority Searches (often called CON29) reveal planning history,
enforcement actions, road adoption status, and other local government
information that affects property transactions.
"""

from pydantic import BaseModel, Field


class LocalAuthoritySearchExtraction(BaseModel):
    """
    Structured extraction from Local Authority Search documents.
    
    Covers key areas of conveyancing concern:
    - Planning permissions (approved, pending, refused)
    - Enforcement notices (unauthorized development)
    - Planning breaches (non-compliance with conditions)
    - Road adoption (whether roads are publicly maintained)
    - Compulsory purchase orders (government acquisition powers)
    """
    
    planning_permissions: list[str] = Field(
        default_factory=list,
        description="Planning permissions affecting the property (approved, pending, refused)"
    )
    
    enforcement_notices: list[str] = Field(
        default_factory=list,
        description="Enforcement notices issued against the property"
    )
    
    planning_breaches: list[str] = Field(
        default_factory=list,
        description="Planning condition breaches or non-compliance issues"
    )
    
    road_adoption_issues: list[str] = Field(
        default_factory=list,
        description="Road adoption status issues (unadopted roads, adoption schemes)"
    )
    
    compulsory_purchase_orders: list[str] = Field(
        default_factory=list,
        description="Compulsory purchase orders affecting the property"
    )
    
    further_action_required: bool | None = Field(
        default=None,
        description="Whether further enquiries or actions are recommended"
    )
    
    source_sections: list[str] = Field(
        default_factory=list,
        description="Document sections from which data was extracted"
    )


class LocalAuthorityChunkExtraction(BaseModel):
    """
    LLM extraction result from a single text chunk.
    Used for aggregating findings across multiple chunks.
    """
    
    planning_permissions: list[str] = Field(default_factory=list)
    enforcement_notices: list[str] = Field(default_factory=list)
    planning_breaches: list[str] = Field(default_factory=list)
    road_adoption_issues: list[str] = Field(default_factory=list)
    compulsory_purchase_orders: list[str] = Field(default_factory=list)
    further_action_required: bool | None = None
