"""
TA6 Property Information Form risk detection rules.

Implements rule-based risk assessment for TA6 seller disclosures.
All risk decisions are deterministic and auditable.

Design principles:
- NO LLM/ML used for risk decisions
- Each rule is explicit and documented
- Rules are based on conveyancing law and practice
- Severity levels are conservative (err on side of caution)

Legal context:
TA6 forms contain seller disclosures about property conditions,
disputes, alterations, and other matters. These rules flag
issues that require solicitor attention or buyer awareness.

Risk Categories:
- BOUNDARY_ISSUES: Disputes, unclear ownership, moved structures
- DISPUTES_COMPLAINTS: Neighbour issues, complaints, claims
- NOTICES_PROPOSALS: Government notices, road schemes, CPO
- ALTERATIONS: Unauthorized work, missing consents, building regs
- ENVIRONMENTAL: Flooding, contamination, Japanese knotweed
- SERVICES: Shared utilities, private drainage, access issues
- OCCUPIERS: Third party rights, tenants, lodgers
- INSURANCE: Insurability concerns, claims history
"""

from typing import List, Tuple
from pydantic import BaseModel, Field
from enum import Enum

from nomoros_ai.models.ta6 import TA6ExtractionResult, TA6Section, TA6Question


class TA6RiskSeverity(str, Enum):
    """Risk severity levels for TA6 issues."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TA6Risk(BaseModel):
    """A single risk identified from TA6 analysis."""
    category: str = Field(..., description="Risk category (e.g., 'Alterations', 'Disputes')")
    severity: TA6RiskSeverity = Field(..., description="Risk severity level")
    description: str = Field(..., description="Human-readable risk description")
    section: str = Field(..., description="TA6 section where issue was found")
    question_id: str | None = Field(None, description="Specific question reference")
    legal_rationale: str = Field(..., description="Why this is a risk")
    recommended_action: str = Field(..., description="What the solicitor should do")
    evidence: str | None = Field(None, description="Quote from form supporting this risk")


class TA6SeverityBreakdown(BaseModel):
    """Count of risks by severity."""
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class TA6RiskSummary(BaseModel):
    """Summary of all risks identified in TA6."""
    total_risks: int = Field(0, description="Total number of risks identified")
    highest_severity: TA6RiskSeverity = Field(TA6RiskSeverity.INFO, description="Highest severity found")
    severity_breakdown: TA6SeverityBreakdown = Field(default_factory=TA6SeverityBreakdown)
    key_issues: List[str] = Field(default_factory=list, description="Summary of key issues")
    clean_areas: List[str] = Field(default_factory=list, description="Areas with no concerns")


class TA6RiskAnalyzer:
    """
    Rule-based risk analyzer for TA6 Property Information Forms.
    
    Applies deterministic rules to identify risks in seller disclosures.
    Each rule checks specific TA6 sections and answers for known risk patterns.
    """
    
    SECTION_KEYWORDS = {
        "boundaries": ["boundary", "boundaries", "fence", "hedge", "wall"],
        "disputes": ["dispute", "complaint", "claim", "threat", "neighbour"],
        "notices": ["notice", "proposal", "letter", "road scheme", "compulsory"],
        "alterations": ["alteration", "planning", "building control", "extension", "conversion"],
        "guarantees": ["guarantee", "warranty", "certificate"],
        "insurance": ["insurance", "insurable", "claim", "premium"],
        "environmental": ["environmental", "flood", "contamination", "knotweed", "radon"],
        "services": ["service", "utility", "gas", "electric", "water", "drainage"],
        "occupiers": ["occupier", "tenant", "lodger", "occupy"],
        "parking": ["parking", "garage", "driveway"],
        "charges": ["charge", "rent charge", "service charge", "maintenance"],
        "rights": ["right", "easement", "access", "shared", "arrangement"],
        "transaction": ["sale", "transaction", "failed", "previous"],
    }
    
    def analyze(self, extraction: TA6ExtractionResult) -> Tuple[TA6RiskSummary, List[TA6Risk]]:
        """
        Analyze TA6 extraction for risks.
        
        Args:
            extraction: Structured TA6 extraction result
            
        Returns:
            Tuple of (TA6RiskSummary, list of TA6Risk objects)
        """
        risks: List[TA6Risk] = []
        clean_areas: List[str] = []
        
        for section in extraction.sections:
            section_risks = self._analyze_section(section)
            if section_risks:
                risks.extend(section_risks)
            else:
                clean_areas.append(section.section_name)
        
        risks.extend(self._check_contradictions(extraction))
        risks.extend(self._check_missing_attachments(extraction))
        risks.extend(self._check_unclear_answers(extraction))
        
        summary = self._build_summary(risks, clean_areas)
        return summary, risks
    
    def _analyze_section(self, section: TA6Section) -> List[TA6Risk]:
        """Analyze a single TA6 section for risks."""
        risks: List[TA6Risk] = []
        section_lower = section.section_name.lower()
        
        if self._matches_category(section_lower, "boundaries"):
            risks.extend(self._check_boundary_risks(section))
        elif self._matches_category(section_lower, "disputes"):
            risks.extend(self._check_dispute_risks(section))
        elif self._matches_category(section_lower, "notices"):
            risks.extend(self._check_notice_risks(section))
        elif self._matches_category(section_lower, "alterations"):
            risks.extend(self._check_alteration_risks(section))
        elif self._matches_category(section_lower, "environmental"):
            risks.extend(self._check_environmental_risks(section))
        elif self._matches_category(section_lower, "insurance"):
            risks.extend(self._check_insurance_risks(section))
        elif self._matches_category(section_lower, "occupiers"):
            risks.extend(self._check_occupier_risks(section))
        elif self._matches_category(section_lower, "services"):
            risks.extend(self._check_service_risks(section))
        elif self._matches_category(section_lower, "rights"):
            risks.extend(self._check_rights_risks(section))
        elif self._matches_category(section_lower, "transaction"):
            risks.extend(self._check_transaction_risks(section))
        
        return risks
    
    def _matches_category(self, text: str, category: str) -> bool:
        """Check if text matches a category by keywords."""
        keywords = self.SECTION_KEYWORDS.get(category, [])
        return any(kw in text for kw in keywords)
    
    def _check_boundary_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for boundary-related risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            details = (q.details or "").lower()
            question_text = (q.question_text or "").lower()
            
            if "dispute" in question_text and answer == "yes":
                risks.append(TA6Risk(
                    category="Boundary Disputes",
                    severity=TA6RiskSeverity.HIGH,
                    description="Seller discloses boundary dispute",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Boundary disputes can affect title insurance, marketability, and may require legal resolution",
                    recommended_action="Obtain full details of dispute, review any correspondence, consider indemnity insurance",
                    evidence=q.answer_raw
                ))
            
            if "moved" in question_text and answer == "yes":
                risks.append(TA6Risk(
                    category="Boundary Changes",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Boundary structures have been moved during ownership",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Moving boundaries may affect legal title extent and neighbour relations",
                    recommended_action="Verify changes match title plan, check for neighbour consent",
                    evidence=q.answer_raw
                ))
            
            if answer == "unknown" or answer == "unclear":
                risks.append(TA6Risk(
                    category="Boundary Uncertainty",
                    severity=TA6RiskSeverity.LOW,
                    description="Seller unsure about boundary ownership",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Unclear boundaries may lead to future disputes",
                    recommended_action="Review title plan and deeds for boundary definitions",
                    evidence=q.answer_raw
                ))
        
        return risks
    
    def _check_dispute_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for dispute and complaint risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            
            if answer == "yes":
                risks.append(TA6Risk(
                    category="Disputes & Complaints",
                    severity=TA6RiskSeverity.HIGH,
                    description="Seller discloses complaints or disputes affecting property",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Ongoing disputes may affect enjoyment of property and could continue after purchase",
                    recommended_action="Obtain full details, review correspondence, assess impact on buyer",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_notice_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for notices and proposals risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            
            if answer == "yes":
                if "compulsory purchase" in question_text:
                    risks.append(TA6Risk(
                        category="Compulsory Purchase",
                        severity=TA6RiskSeverity.HIGH,
                        description="Property may be subject to compulsory purchase order",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="CPO can result in forced sale at potentially below market value",
                        recommended_action="Obtain full details of CPO, verify with local authority, advise buyer of risk",
                        evidence=q.details or q.answer_raw
                    ))
                elif "road" in question_text:
                    risks.append(TA6Risk(
                        category="Road Schemes",
                        severity=TA6RiskSeverity.MEDIUM,
                        description="Road scheme or access changes may affect property",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Road changes can affect access, noise, and property value",
                        recommended_action="Obtain details of scheme, verify with highways authority",
                        evidence=q.details or q.answer_raw
                    ))
                else:
                    risks.append(TA6Risk(
                        category="Notices Received",
                        severity=TA6RiskSeverity.MEDIUM,
                        description="Seller has received official notices affecting property",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Official notices may impose obligations or restrictions",
                        recommended_action="Obtain copies of all notices, assess ongoing implications",
                        evidence=q.details or q.answer_raw
                    ))
        
        return risks
    
    def _check_alteration_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for alterations and building control risks."""
        risks = []
        has_alterations = False
        has_consent = True
        
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            details = (q.details or "").lower()
            
            if "altered" in question_text or "extension" in question_text:
                if answer == "yes":
                    has_alterations = True
            
            if "consent" in question_text or "approval" in question_text:
                if answer == "no" or "not required" not in details:
                    if "no" in answer or answer == "unknown":
                        has_consent = False
        
        if has_alterations and not has_consent:
            risks.append(TA6Risk(
                category="Unauthorized Alterations",
                severity=TA6RiskSeverity.HIGH,
                description="Property has alterations that may lack required consents",
                section=section.section_name,
                question_id=None,
                legal_rationale="Unauthorized building work may be subject to enforcement action and affect insurance/mortgage",
                recommended_action="Request all building control certificates, planning permissions; consider indemnity insurance",
                evidence=None
            ))
        
        for q in section.questions:
            details = (q.details or "").lower()
            if "conservatory" in details or "extension" in details or "loft" in details:
                if "building reg" not in details and "certificate" not in details:
                    risks.append(TA6Risk(
                        category="Building Regulations",
                        severity=TA6RiskSeverity.MEDIUM,
                        description=f"Alteration may require building regulations sign-off: {q.details}",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Building work without sign-off may not comply with safety standards",
                        recommended_action="Request completion certificate or obtain indemnity insurance",
                        evidence=q.details
                    ))
        
        return risks
    
    def _check_environmental_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for environmental risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            
            if answer == "yes":
                if "flood" in question_text:
                    risks.append(TA6Risk(
                        category="Flood Risk",
                        severity=TA6RiskSeverity.HIGH,
                        description="Property has flooded or is in flood risk area",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Flooding affects insurance availability, property value, and habitability",
                        recommended_action="Obtain environmental search, verify insurance availability, advise buyer of risk",
                        evidence=q.details or q.answer_raw
                    ))
                
                if "knotweed" in question_text or "japanese" in question_text:
                    risks.append(TA6Risk(
                        category="Japanese Knotweed",
                        severity=TA6RiskSeverity.HIGH,
                        description="Japanese knotweed present at property",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Knotweed is invasive, expensive to treat, and affects mortgage availability",
                        recommended_action="Obtain specialist survey, treatment plan with guarantee, verify lender acceptance",
                        evidence=q.details or q.answer_raw
                    ))
                
                if "contamination" in question_text:
                    risks.append(TA6Risk(
                        category="Land Contamination",
                        severity=TA6RiskSeverity.HIGH,
                        description="Seller aware of land contamination",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Contamination may affect health, require remediation, and reduce value",
                        recommended_action="Obtain environmental report, assess remediation requirements",
                        evidence=q.details or q.answer_raw
                    ))
        
        return risks
    
    def _check_insurance_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for insurance-related risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            
            if "insurable" in question_text or "insurance" in question_text:
                if answer == "yes":
                    risks.append(TA6Risk(
                        category="Insurance Concerns",
                        severity=TA6RiskSeverity.HIGH,
                        description="Property may have insurance difficulties",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Insurance issues may affect mortgage approval and property protection",
                        recommended_action="Verify current insurance terms, obtain quotes for buyer, check lender requirements",
                        evidence=q.details or q.answer_raw
                    ))
            
            if "claim" in question_text and answer == "yes":
                risks.append(TA6Risk(
                    category="Insurance Claims History",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Previous insurance claims on property",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Claims history may affect future premiums or coverage",
                    recommended_action="Obtain details of claims, advise buyer to check premium impact",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_occupier_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for occupier-related risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            
            if answer == "yes":
                risks.append(TA6Risk(
                    category="Third Party Occupiers",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Property has occupiers other than sellers",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Third parties may have rights of occupation that survive the sale",
                    recommended_action="Obtain details of occupiers, verify they will vacate, check for tenancy rights",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_service_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for services and utilities risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            details = (q.details or "").lower()
            
            if "shared" in question_text and answer == "yes":
                risks.append(TA6Risk(
                    category="Shared Services",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Property shares utilities or services with neighbours",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Shared services require maintenance agreements and may cause disputes",
                    recommended_action="Verify sharing arrangements, check for formal agreements, review cost sharing",
                    evidence=q.details or q.answer_raw
                ))
            
            if "private" in details and ("drain" in details or "septic" in details):
                risks.append(TA6Risk(
                    category="Private Drainage",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Property has private drainage system",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Private drainage requires maintenance and may not meet current standards",
                    recommended_action="Verify system condition, check for registration, review maintenance costs",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_rights_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for rights and arrangements risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            
            if answer == "yes":
                risks.append(TA6Risk(
                    category="Informal Arrangements",
                    severity=TA6RiskSeverity.LOW,
                    description="Informal arrangements exist with neighbours or others",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Informal arrangements may not bind future owners or neighbours",
                    recommended_action="Document arrangements, consider formalising in deed, advise buyer",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_transaction_risks(self, section: TA6Section) -> List[TA6Risk]:
        """Check for transaction history risks."""
        risks = []
        for q in section.questions:
            answer = (q.answer_normalised or "").lower()
            question_text = (q.question_text or "").lower()
            
            if "failed" in question_text and answer == "yes":
                risks.append(TA6Risk(
                    category="Failed Previous Sales",
                    severity=TA6RiskSeverity.MEDIUM,
                    description="Previous sale attempts have failed",
                    section=section.section_name,
                    question_id=q.question_id,
                    legal_rationale="Failed sales may indicate underlying issues with the property",
                    recommended_action="Obtain full details of why sales failed, verify issues have been resolved",
                    evidence=q.details or q.answer_raw
                ))
        
        return risks
    
    def _check_contradictions(self, extraction: TA6ExtractionResult) -> List[TA6Risk]:
        """Flag detected contradictions as risks."""
        risks = []
        for contradiction in extraction.contradictions:
            risks.append(TA6Risk(
                category="Contradiction",
                severity=TA6RiskSeverity.HIGH,
                description=contradiction.description,
                section="Multiple Sections",
                question_id=None,
                legal_rationale="Contradictory information may indicate errors or concealment",
                recommended_action="Raise with seller for clarification before exchange",
                evidence=str(contradiction.items) if contradiction.items else None
            ))
        
        return risks
    
    def _check_missing_attachments(self, extraction: TA6ExtractionResult) -> List[TA6Risk]:
        """Flag missing attachments as risks."""
        risks = []
        for attachment in extraction.missing_or_referenced_attachments:
            risks.append(TA6Risk(
                category="Missing Documentation",
                severity=TA6RiskSeverity.MEDIUM,
                description=f"Referenced document not provided: {attachment.get('description', 'Unknown')}",
                section=attachment.get("section", "Unknown"),
                question_id=None,
                legal_rationale="Missing documents may contain material information",
                recommended_action="Request document from seller before exchange",
                evidence=None
            ))
        
        return risks
    
    def _check_unclear_answers(self, extraction: TA6ExtractionResult) -> List[TA6Risk]:
        """Flag unclear or missing answers."""
        risks = []
        for section in extraction.sections:
            for q in section.questions:
                if q.answer_status == "unclear" or q.answer_status == "missing":
                    risks.append(TA6Risk(
                        category="Incomplete Information",
                        severity=TA6RiskSeverity.LOW,
                        description=f"Answer unclear or missing: {q.question_text[:50]}...",
                        section=section.section_name,
                        question_id=q.question_id,
                        legal_rationale="Incomplete information prevents proper due diligence",
                        recommended_action="Raise additional enquiry with seller",
                        evidence=None
                    ))
        
        return risks
    
    def _build_summary(self, risks: List[TA6Risk], clean_areas: List[str]) -> TA6RiskSummary:
        """Build risk summary from individual risks."""
        breakdown = TA6SeverityBreakdown()
        highest = TA6RiskSeverity.INFO
        key_issues = []
        
        severity_order = [TA6RiskSeverity.INFO, TA6RiskSeverity.LOW, TA6RiskSeverity.MEDIUM, TA6RiskSeverity.HIGH]
        
        for risk in risks:
            if risk.severity == TA6RiskSeverity.HIGH:
                breakdown.high += 1
                key_issues.append(f"[HIGH] {risk.description}")
            elif risk.severity == TA6RiskSeverity.MEDIUM:
                breakdown.medium += 1
                if len(key_issues) < 5:
                    key_issues.append(f"[MEDIUM] {risk.description}")
            elif risk.severity == TA6RiskSeverity.LOW:
                breakdown.low += 1
            else:
                breakdown.info += 1
            
            if severity_order.index(risk.severity) > severity_order.index(highest):
                highest = risk.severity
        
        return TA6RiskSummary(
            total_risks=len(risks),
            highest_severity=highest,
            severity_breakdown=breakdown,
            key_issues=key_issues[:10],
            clean_areas=clean_areas[:5]
        )
