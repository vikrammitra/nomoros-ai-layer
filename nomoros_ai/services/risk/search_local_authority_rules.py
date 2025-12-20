"""
Deterministic risk rules for Local Authority Search documents.

IMPORTANT: All severity decisions are made HERE, not by the LLM.
The LLM only assists with extraction - this layer applies the rules.

Risk categories for Local Authority Searches:
- Planning enforcement (unauthorised development)
- Planning breaches (non-compliance with conditions)
- Road adoption (maintenance liability, access rights)
- Compulsory purchase (property acquisition by authorities)
"""

from nomoros_ai.models.search_local_authority import LocalAuthoritySearchExtraction
from nomoros_ai.models.title import RiskSummary, RiskSeverity, SeverityBreakdown


class LocalAuthorityRiskAnalyzer:
    """
    Applies deterministic rules to Local Authority Search extractions.
    
    Risk severity rules:
    🔴 HIGH:
    - Enforcement notice present (unauthorized development)
    - Planning breach present (condition non-compliance)
    - Compulsory purchase order (property may be acquired)
    
    🟠 MEDIUM:
    - Section 106 agreement (planning obligations/restrictions)
    - Unadopted road (ongoing maintenance liability)
    - Further action required (outstanding enquiries)
    
    🟢 LOW (informational):
    - Smoke control order (common, rarely impacts transactions)
    - Tree preservation order (affects tree removal rights)
    """
    
    CATEGORY = "Searches – Local Authority"
    
    def analyze(
        self,
        extraction: LocalAuthoritySearchExtraction
    ) -> tuple[RiskSummary, list[dict]]:
        """
        Analyze extraction and return risk summary.
        
        Args:
            extraction: LocalAuthoritySearchExtraction from LLM extraction
            
        Returns:
            Tuple of (RiskSummary, list of detailed risk records)
        """
        risks: list[dict] = []
        risk_descriptions: list[str] = []
        
        # ============================================================
        # HIGH SEVERITY RISKS
        # ============================================================
        
        # Enforcement notices - 🔴 HIGH
        # Legal basis: Enforcement notices indicate unauthorized development
        # which may need to be remedied or could affect property value
        if extraction.enforcement_notices:
            for notice in extraction.enforcement_notices:
                risks.append({
                    "category": self.CATEGORY,
                    "severity": "High",
                    "issue": "Enforcement notice",
                    "description": notice,
                    "legal_rationale": "Enforcement notices indicate unauthorized development that may require remediation"
                })
                risk_descriptions.append(
                    f"Enforcement notice identified: {notice[:100]}..." 
                    if len(notice) > 100 else f"Enforcement notice identified: {notice}"
                )
        
        # Planning breaches - 🔴 HIGH
        # Legal basis: Breach of planning conditions may result in enforcement
        # action and could affect property insurance and mortgage lending
        if extraction.planning_breaches:
            for breach in extraction.planning_breaches:
                risks.append({
                    "category": self.CATEGORY,
                    "severity": "High",
                    "issue": "Planning breach",
                    "description": breach,
                    "legal_rationale": "Planning condition breaches may result in enforcement action"
                })
                risk_descriptions.append(
                    f"Planning condition breach: {breach[:100]}..."
                    if len(breach) > 100 else f"Planning condition breach: {breach}"
                )
        
        # Compulsory purchase orders - 🔴 HIGH
        # Legal basis: CPO means the property may be compulsorily acquired
        # by a public authority, fundamentally affecting ownership
        if extraction.compulsory_purchase_orders:
            for cpo in extraction.compulsory_purchase_orders:
                risks.append({
                    "category": self.CATEGORY,
                    "severity": "High",
                    "issue": "Compulsory purchase order",
                    "description": cpo,
                    "legal_rationale": "CPO may result in compulsory acquisition of property"
                })
                risk_descriptions.append(
                    f"Compulsory purchase order: {cpo[:100]}..."
                    if len(cpo) > 100 else f"Compulsory purchase order: {cpo}"
                )
        
        # ============================================================
        # MEDIUM SEVERITY RISKS
        # ============================================================
        
        # Section 106 agreements - 🟠 MEDIUM
        # Legal basis: S106 agreements impose planning obligations that run with the land
        # May require financial contributions or restrict future development
        if extraction.local_land_charges:
            for charge in extraction.local_land_charges:
                charge_lower = charge.lower()
                
                # Section 106 agreements are MEDIUM - impose ongoing obligations
                if "section 106" in charge_lower or "s106" in charge_lower or "planning agreement" in charge_lower:
                    risks.append({
                        "category": self.CATEGORY,
                        "severity": "Medium",
                        "issue": "Section 106 agreement",
                        "description": charge,
                        "legal_rationale": "Section 106 agreements impose planning obligations that run with the land"
                    })
                    risk_descriptions.append(
                        f"Section 106 agreement: {charge[:100]}..."
                        if len(charge) > 100 else f"Section 106 agreement: {charge}"
                    )
                
                # Tree preservation orders are LOW but informational
                elif "tree preservation" in charge_lower or "tpo" in charge_lower:
                    risks.append({
                        "category": self.CATEGORY,
                        "severity": "Low",
                        "issue": "Tree preservation order",
                        "description": charge,
                        "legal_rationale": "TPO restricts removal or works to protected trees"
                    })
                    risk_descriptions.append(
                        f"Tree preservation order: {charge[:100]}..."
                        if len(charge) > 100 else f"Tree preservation order: {charge}"
                    )
                
                # Smoke control orders are LOW - informational
                elif "smoke control" in charge_lower or "clean air" in charge_lower:
                    risks.append({
                        "category": self.CATEGORY,
                        "severity": "Low",
                        "issue": "Smoke control order",
                        "description": charge,
                        "legal_rationale": "Smoke control order restricts burning of certain fuels"
                    })
                    risk_descriptions.append(
                        f"Smoke control order: {charge[:80]}..."
                        if len(charge) > 80 else f"Smoke control order: {charge}"
                    )
                
                # Financial charges are MEDIUM - may affect property
                elif "financial" in charge_lower or "charge" in charge_lower:
                    risks.append({
                        "category": self.CATEGORY,
                        "severity": "Medium",
                        "issue": "Financial charge",
                        "description": charge,
                        "legal_rationale": "Financial charges registered against the property"
                    })
                    risk_descriptions.append(
                        f"Financial charge: {charge[:100]}..."
                        if len(charge) > 100 else f"Financial charge: {charge}"
                    )
        
        # Road adoption issues - 🟠 MEDIUM
        # Legal basis: Unadopted roads mean the property owner may be liable
        # for maintenance costs and the road may not be publicly maintained
        if extraction.road_adoption_issues:
            for issue in extraction.road_adoption_issues:
                risks.append({
                    "category": self.CATEGORY,
                    "severity": "Medium",
                    "issue": "Road adoption",
                    "description": issue,
                    "legal_rationale": "Unadopted roads may involve ongoing maintenance liability"
                })
                risk_descriptions.append(
                    f"Road adoption issue: {issue[:100]}..."
                    if len(issue) > 100 else f"Road adoption issue: {issue}"
                )
        
        # Further action required - 🟠 MEDIUM
        # Legal basis: Document recommends further enquiries, indicating
        # incomplete information that should be resolved before exchange
        if extraction.further_action_required:
            risks.append({
                "category": self.CATEGORY,
                "severity": "Medium",
                "issue": "Further enquiries required",
                "description": "The search indicates further enquiries are recommended",
                "legal_rationale": "Outstanding enquiries should be resolved before exchange of contracts"
            })
            risk_descriptions.append(
                "Further enquiries recommended - additional information required"
            )
        
        # ============================================================
        # CALCULATE OVERALL SEVERITY
        # ============================================================
        
        high_count = sum(1 for r in risks if r["severity"] == "High")
        medium_count = sum(1 for r in risks if r["severity"] == "Medium")
        low_count = sum(1 for r in risks if r["severity"] == "Low")
        
        severity_breakdown = SeverityBreakdown(
            high=high_count,
            medium=medium_count,
            low=low_count
        )
        
        # Overall severity is the highest individual severity
        if high_count > 0:
            overall_severity = RiskSeverity.HIGH
        elif medium_count > 0:
            overall_severity = RiskSeverity.MEDIUM
        else:
            overall_severity = RiskSeverity.LOW
        
        summary = RiskSummary(
            category=self.CATEGORY,
            severity=overall_severity,
            risk_count=len(risks),
            risks=risk_descriptions,
            severity_breakdown=severity_breakdown,
            confidence=1.0  # Deterministic rule-based analysis = 100% confidence
        )
        
        return summary, risks
