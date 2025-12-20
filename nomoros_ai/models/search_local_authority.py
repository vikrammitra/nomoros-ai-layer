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
    - Local land charges (Section 106, smoke control, tree preservation)
    - Planning register entries (approved, pending, refused, withdrawn)
    - Enforcement notices (unauthorized development)
    - Planning breaches (non-compliance with conditions)
    - Road adoption (whether roads are publicly maintained)
    - Compulsory purchase orders (government acquisition powers)
    - Community Infrastructure Levy (CIL) liability
    """
    
    local_land_charges: list[str] = Field(
        default_factory=list,
        description="Local Land Charge register entries (Section 106 agreements, smoke control orders, tree preservation orders, financial charges)"
    )
    
    planning_register_entries: list[str] = Field(
        default_factory=list,
        description="Planning register entries (applications granted, refused, pending, withdrawn with refs and dates)"
    )
    
    enforcement_notices: list[str] = Field(
        default_factory=list,
        description="Enforcement notices or stop notices issued against the property"
    )
    
    planning_breaches: list[str] = Field(
        default_factory=list,
        description="Planning condition breaches or non-compliance issues"
    )
    
    road_adoption_issues: list[str] = Field(
        default_factory=list,
        description="Road adoption status issues (unadopted roads, private roads, adoption schemes)"
    )
    
    compulsory_purchase_orders: list[str] = Field(
        default_factory=list,
        description="Compulsory purchase orders affecting the property"
    )
    
    cil_liability: list[str] = Field(
        default_factory=list,
        description="Community Infrastructure Levy (CIL) mentions, liability, or charging schedule references"
    )
    
    further_action_required: bool | None = Field(
        default=None,
        description="Whether further enquiries or actions are recommended"
    )
    
    further_action_details: list[str] = Field(
        default_factory=list,
        description="Specific details about recommended further enquiries or actions"
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
    
    local_land_charges: list[str] = Field(default_factory=list)
    planning_register_entries: list[str] = Field(default_factory=list)
    enforcement_notices: list[str] = Field(default_factory=list)
    planning_breaches: list[str] = Field(default_factory=list)
    road_adoption_issues: list[str] = Field(default_factory=list)
    compulsory_purchase_orders: list[str] = Field(default_factory=list)
    cil_liability: list[str] = Field(default_factory=list)
    further_action_required: bool | None = None
    further_action_details: list[str] = Field(default_factory=list)
