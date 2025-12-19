"""
Title Register risk detection rules.

Implements rule-based risk assessment for Title Register data.
All risk decisions are deterministic and auditable.

Design principles:
- NO LLM/ML used for risk decisions
- Each rule is explicit and documented
- Rules are based on conveyancing law and practice
- Severity levels are conservative (err on side of caution)

Legal context:
These rules are designed to flag common issues that arise in
residential conveyancing. They should be reviewed by a solicitor
before being used in production.
"""

from nomoros_ai.models.title import (
    TitleRegisterExtraction,
    TitleClass,
    TitleRisk,
    RiskSeverity,
    RiskSummary
)


class TitleRiskAnalyzer:
    """
    Rule-based risk analyzer for Title Register data.
    
    This class applies deterministic rules to identify risks
    in title data. Each rule is documented with:
    - Legal rationale
    - Severity justification
    - Recommended action
    
    Risk categories:
    - Title & Ownership: Issues with the quality of title
    - Restrictions: Limitations on dealing with the property
    - Charges: Financial encumbrances
    """
    
    def analyze(self, extraction: TitleRegisterExtraction) -> tuple[RiskSummary, list[TitleRisk]]:
        """
        Analyze extracted title data for risks.
        
        Args:
            extraction: Structured data from title extraction
            
        Returns:
            Tuple of (RiskSummary, list of detailed TitleRisk objects)
        """
        risks: list[TitleRisk] = []
        
        # Apply each rule
        risks.extend(self._check_possessory_title(extraction))
        risks.extend(self._check_restrictions(extraction))
        risks.extend(self._check_qualified_title(extraction))
        risks.extend(self._check_unknown_title_class(extraction))
        
        # Determine highest severity
        highest_severity = self._get_highest_severity(risks)
        
        # Create summary
        summary = RiskSummary(
            category="Title & Ownership",
            severity=highest_severity,
            risk_count=len(risks),
            risks=[r.description for r in risks],
            confidence=self._calculate_confidence(extraction, risks)
        )
        
        return summary, risks
    
    def _check_possessory_title(self, extraction: TitleRegisterExtraction) -> list[TitleRisk]:
        """
        Rule: Possessory title is HIGH risk.
        
        Legal rationale:
        Possessory title means the Land Registry has registered the
        proprietor based on their possession of the land, not on
        documentary proof of title. This carries significant risks:
        
        1. The true owner could emerge and claim the property
        2. Lenders are often reluctant to lend on possessory titles
        3. Indemnity insurance is typically required
        
        The title may upgrade to absolute after 12 years of
        unchallenged possession (squatter's rights/adverse possession).
        """
        if extraction.title_class == TitleClass.POSSESSORY:
            return [TitleRisk(
                category="Title & Ownership",
                severity=RiskSeverity.HIGH,
                description="Title is possessory; indemnity insurance likely required",
                recommendation=(
                    "Obtain a possessory title indemnity policy. "
                    "Check if title can be upgraded to absolute (12+ years registered). "
                    "Confirm lender will accept possessory title."
                )
            )]
        return []
    
    def _check_restrictions(self, extraction: TitleRegisterExtraction) -> list[TitleRisk]:
        """
        Rule: Restrictions on title are MEDIUM risk.
        
        Legal rationale:
        Restrictions limit how the property can be sold or charged.
        Common types include:
        
        1. Consent restrictions (third party must agree to sale)
        2. Certificate restrictions (conveyancer must certify compliance)
        3. Charging restrictions (limitations on mortgages)
        
        While not necessarily problematic, restrictions require:
        - Identification of the restriction holder
        - Understanding of what triggers the restriction
        - Obtaining necessary consents/certificates before completion
        
        Failure to comply with restrictions will prevent registration
        of the new owner at the Land Registry.
        """
        risks = []
        
        if extraction.restrictions:
            num_restrictions = len(extraction.restrictions)
            
            # Build description based on number of restrictions
            if num_restrictions == 1:
                desc = "Restriction on disposition identified (1 restriction)"
            else:
                desc = f"Multiple restrictions on disposition identified ({num_restrictions} restrictions)"
            
            risks.append(TitleRisk(
                category="Title & Ownership",
                severity=RiskSeverity.MEDIUM,
                description=desc,
                recommendation=(
                    "Review each restriction to identify what consent/certificate is required. "
                    "Contact restriction holders early to avoid delays. "
                    "Ensure compliance certificates are obtained before completion."
                )
            ))
            
            # Check for specific high-risk restriction patterns
            for restriction in extraction.restrictions:
                if restriction.parties_involved:
                    for party in restriction.parties_involved:
                        if "limited" in party.lower() or "ltd" in party.lower():
                            risks.append(TitleRisk(
                                category="Title & Ownership",
                                severity=RiskSeverity.MEDIUM,
                                description=f"Third party consent required: {party}",
                                recommendation=(
                                    f"Contact {party} to understand their requirements "
                                    "and timescales for providing consent."
                                )
                            ))
                            break  # Only add one per restriction
        
        return risks
    
    def _check_qualified_title(self, extraction: TitleRegisterExtraction) -> list[TitleRisk]:
        """
        Rule: Qualified title is HIGH risk.
        
        Legal rationale:
        Qualified title means the Land Registry has excluded a
        specific defect from their guarantee. The title is registered
        subject to that defect, which could affect:
        
        1. The validity of the proprietor's ownership
        2. Third party rights over the property
        3. The ability to obtain mortgage finance
        
        The nature of the qualification should be carefully reviewed.
        """
        if extraction.title_class == TitleClass.QUALIFIED:
            return [TitleRisk(
                category="Title & Ownership",
                severity=RiskSeverity.HIGH,
                description="Title is qualified; specific defect excluded from Land Registry guarantee",
                recommendation=(
                    "Review the nature of the qualification in the register. "
                    "Consider whether the defect is acceptable to the buyer and lender. "
                    "Indemnity insurance may be required."
                )
            )]
        return []
    
    def _check_unknown_title_class(self, extraction: TitleRegisterExtraction) -> list[TitleRisk]:
        """
        Rule: Unable to determine title class is LOW risk.
        
        This typically indicates an extraction issue rather than
        a legal problem, but should be flagged for manual review.
        """
        if extraction.title_class == TitleClass.UNKNOWN:
            return [TitleRisk(
                category="Title & Ownership",
                severity=RiskSeverity.LOW,
                description="Unable to determine title class; manual review recommended",
                recommendation=(
                    "Manually review the title register to confirm the class of title. "
                    "Most residential titles are Absolute."
                )
            )]
        return []
    
    def _get_highest_severity(self, risks: list[TitleRisk]) -> RiskSeverity:
        """
        Determine the highest severity among all risks.
        
        Priority: HIGH > MEDIUM > LOW
        """
        if not risks:
            return RiskSeverity.LOW
        
        severity_order = {
            RiskSeverity.HIGH: 3,
            RiskSeverity.MEDIUM: 2,
            RiskSeverity.LOW: 1
        }
        
        highest = max(risks, key=lambda r: severity_order[r.severity])
        return highest.severity
    
    def _calculate_confidence(
        self,
        extraction: TitleRegisterExtraction,
        risks: list[TitleRisk]
    ) -> float:
        """
        Calculate confidence score for the risk assessment.
        
        Confidence is based on:
        - Quality of extraction (how many fields populated)
        - Clarity of risk indicators
        
        Returns:
            Float between 0.0 and 1.0
        """
        # Base confidence from extraction quality
        extraction_score = 0.0
        
        if extraction.title_number:
            extraction_score += 0.2
        if extraction.title_class != TitleClass.UNKNOWN:
            extraction_score += 0.3
        if extraction.proprietors:
            extraction_score += 0.2
        if extraction.property_description:
            extraction_score += 0.2
        if extraction.edition_date:
            extraction_score += 0.1
        
        # Confidence is capped at 0.95 for rule-based analysis
        # (acknowledging limitations of automated assessment)
        return min(extraction_score, 0.95)
