"""
Title Register models for structured extraction and risk analysis.

These Pydantic models define the structure for HM Land Registry
Title Register data extraction and risk assessment.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class TitleClass(str, Enum):
    """
    Classification of title types in the Land Registry.
    
    Different title classes carry different levels of legal certainty:
    - ABSOLUTE: Highest level of certainty, most common
    - GOOD_LEASEHOLD: Similar to absolute but for leasehold titles
    - POSSESSORY: Based on possession, not documentary proof - HIGH RISK
    - QUALIFIED: Title subject to some qualification
    """
    ABSOLUTE = "Absolute"
    GOOD_LEASEHOLD = "Good Leasehold"
    POSSESSORY = "Possessory"
    QUALIFIED = "Qualified"
    UNKNOWN = "Unknown"


class Proprietor(BaseModel):
    """
    A registered proprietor (owner) of the title.
    
    Attributes:
        name: Full name of the proprietor
        address: Address as shown on the register (may differ from property)
    """
    name: str
    address: Optional[str] = None


class Restriction(BaseModel):
    """
    A restriction on the title affecting disposal rights.
    
    Restrictions appear in the Proprietorship Register (Section B) and
    limit how the property can be sold or charged.
    
    Attributes:
        date_registered: Date the restriction was entered
        description: Full text of the restriction
        parties_involved: Any third parties named in the restriction
    """
    date_registered: Optional[str] = None
    description: str
    parties_involved: Optional[list[str]] = None


class TitleRegisterExtraction(BaseModel):
    """
    Structured extraction from an HM Land Registry Title Register.
    
    This model captures the key information from the three register sections:
    - Section A (Property Register): Property description
    - Section B (Proprietorship Register): Ownership and restrictions
    - Section C (Charges Register): Mortgages and encumbrances
    
    Attributes:
        title_number: Unique Land Registry reference (e.g., BK480212)
        edition_date: Date of the current edition of the register
        property_description: Description from Section A including address
        proprietors: List of registered owners from Section B
        title_class: Classification of the title (Absolute, Possessory, etc.)
        restrictions: List of restrictions affecting disposal
        charges_summary: Summary of any charges in Section C
    """
    title_number: Optional[str] = Field(None, description="Unique Land Registry reference")
    edition_date: Optional[str] = Field(None, description="Edition date of the register")
    property_description: Optional[str] = Field(None, description="Property description from Section A")
    proprietors: list[Proprietor] = Field(default_factory=list, description="List of registered owners")
    title_class: TitleClass = Field(TitleClass.UNKNOWN, description="Classification of title")
    restrictions: list[Restriction] = Field(default_factory=list, description="Restrictions on disposition")
    charges_summary: Optional[str] = Field(None, description="Summary of charges from Section C")


class RiskSeverity(str, Enum):
    """
    Risk severity levels for conveyancing issues.
    
    These levels are designed to be understood by solicitors:
    - HIGH: Requires immediate attention, may block transaction
    - MEDIUM: Should be addressed, may require additional enquiries
    - LOW: Minor issue, note for awareness
    """
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TitleRisk(BaseModel):
    """
    An individual risk identified in the title.
    
    Attributes:
        category: Risk category (e.g., "Title & Ownership")
        severity: Risk severity level
        description: Human-readable explanation for solicitors
        recommendation: Suggested action to address the risk
    """
    category: str = "Title & Ownership"
    severity: RiskSeverity
    description: str
    recommendation: Optional[str] = None


class RiskSummary(BaseModel):
    """
    Summary of all risks identified in a title.
    
    Attributes:
        category: Primary risk category
        severity: Highest severity among all risks
        risk_count: Total number of risks identified
        risks: List of human-readable risk descriptions
        confidence: Confidence score in the assessment (0.0-1.0)
    """
    category: str = "Title & Ownership"
    severity: RiskSeverity
    risk_count: int
    risks: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class TitleRiskResponse(BaseModel):
    """
    Complete response for title risk analysis endpoint.
    
    Attributes:
        document_type: Classification of the document
        extraction: Structured data extracted from the title
        risk_summary: Summary of identified risks
        detailed_risks: Full list of risk objects with recommendations
    """
    document_type: str
    extraction: TitleRegisterExtraction
    risk_summary: RiskSummary
    detailed_risks: list[TitleRisk] = Field(default_factory=list)
