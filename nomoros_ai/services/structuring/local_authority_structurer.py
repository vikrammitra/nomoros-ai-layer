"""
Structuring service for Local Authority Search results.

Converts flat extraction into solicitor-friendly grouped format.
Does NOT change extraction logic, risk rules, or add new findings.
"""

import re
from nomoros_ai.models.search_local_authority import LocalAuthoritySearchExtraction
from nomoros_ai.models.search_local_authority_structured import (
    StructuredLocalAuthorityExtraction,
    GroupedLocalLandCharges,
    LocalLandChargeEntry,
    PlanningRegisterEntry,
    RoadAdoptionFinding,
    CILFinding,
    KeyIssuesSummary,
    IssueLabel,
)


class LocalAuthorityStructurer:
    """
    Structures Local Authority Search extraction for solicitor readability.
    
    This is a presentation layer only - no extraction or risk logic changes.
    """
    
    def structure(
        self,
        extraction: LocalAuthoritySearchExtraction
    ) -> StructuredLocalAuthorityExtraction:
        """
        Convert flat extraction to structured solicitor-friendly format.
        """
        return StructuredLocalAuthorityExtraction(
            key_issues_summary=self._build_key_issues_summary(extraction),
            local_land_charges=self._group_local_land_charges(extraction.local_land_charges),
            planning_register=self._structure_planning_entries(extraction.planning_register_entries),
            road_adoption=self._structure_road_adoption(extraction.road_adoption_issues),
            cil_findings=self._structure_cil_findings(extraction.cil_liability),
            enforcement_notices=extraction.enforcement_notices,
            planning_breaches=extraction.planning_breaches,
            compulsory_purchase_orders=extraction.compulsory_purchase_orders,
            further_action_required=extraction.further_action_required,
            further_action_details=extraction.further_action_details,
        )
    
    def _build_key_issues_summary(
        self,
        extraction: LocalAuthoritySearchExtraction
    ) -> KeyIssuesSummary:
        """
        Build lightweight summary of key issues identified.
        Only references extracted findings - no interpretation.
        """
        issues = []
        no_issues = []
        
        # Section 106 agreements
        s106_count = sum(
            1 for llc in extraction.local_land_charges
            if "section 106" in llc.lower() or "s106" in llc.lower()
        )
        if s106_count > 0:
            issues.append("Section 106 agreement affecting the property")
        
        # Tree preservation orders
        tpo_found = any(
            "tree preservation" in llc.lower() or "tpo" in llc.lower()
            for llc in extraction.local_land_charges
        )
        if tpo_found:
            issues.append("Tree Preservation Order applies")
        
        # Smoke control
        smoke_found = any(
            "smoke control" in llc.lower() or "clean air" in llc.lower()
            for llc in extraction.local_land_charges
        )
        if smoke_found:
            issues.append("Smoke Control Order applies")
        
        # Road adoption issues
        road_issues = [
            r for r in extraction.road_adoption_issues
            if "not" in r.lower() and ("adopted" in r.lower() or "maintainable" in r.lower())
        ]
        if road_issues:
            issues.append("Road serving the property is not publicly adopted")
        
        # CIL
        if extraction.cil_liability:
            issues.append("CIL charging regime applies in this area")
        
        # Enforcement / Breaches
        if extraction.enforcement_notices:
            issues.append("Enforcement notice(s) identified")
        else:
            no_issues.append("No enforcement notices identified")
        
        if extraction.planning_breaches:
            issues.append("Planning breach(es) identified")
        else:
            no_issues.append("No planning breaches identified")
        
        # CPO
        if extraction.compulsory_purchase_orders:
            issues.append("Compulsory Purchase Order affects the property")
        else:
            no_issues.append("No compulsory purchase orders identified")
        
        return KeyIssuesSummary(issues=issues, no_issues_found=no_issues)
    
    def _group_local_land_charges(
        self,
        charges: list[str]
    ) -> GroupedLocalLandCharges:
        """
        Group Local Land Charges by type for easier scanning.
        """
        grouped = GroupedLocalLandCharges()
        
        for charge in charges:
            charge_lower = charge.lower()
            entry = self._parse_llc_entry(charge)
            
            if "section 106" in charge_lower or "s106" in charge_lower or "planning agreement" in charge_lower:
                entry.label = IssueLabel.ONGOING_OBLIGATION
                grouped.section_106_agreements.append(entry)
            elif "tree preservation" in charge_lower or "tpo" in charge_lower:
                entry.label = IssueLabel.USE_RESTRICTION
                grouped.tree_preservation_orders.append(entry)
            elif "smoke control" in charge_lower or "clean air" in charge_lower:
                entry.label = IssueLabel.ENVIRONMENTAL_REGULATION
                grouped.smoke_control_orders.append(entry)
            elif "financial" in charge_lower or "charge" in charge_lower:
                entry.label = IssueLabel.FINANCIAL_LIABILITY
                grouped.financial_charges.append(entry)
            else:
                entry.label = IssueLabel.INFORMATIONAL
                grouped.other_charges.append(entry)
        
        return grouped
    
    def _parse_llc_entry(self, charge: str) -> LocalLandChargeEntry:
        """Parse a charge string to extract date if present."""
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", charge)
        date_registered = date_match.group(1) if date_match else None
        
        return LocalLandChargeEntry(
            description=charge,
            date_registered=date_registered
        )
    
    def _structure_planning_entries(
        self,
        entries: list[str]
    ) -> list[PlanningRegisterEntry]:
        """
        Structure Planning Register entries with explicit fields.
        """
        structured = []
        
        for entry in entries:
            parsed = self._parse_planning_entry(entry)
            structured.append(parsed)
        
        return structured
    
    def _parse_planning_entry(self, entry: str) -> PlanningRegisterEntry:
        """
        Parse a planning entry string into structured format.
        
        Expected formats:
        - "98/43306/FUL - Description - PG/C 21/09/1998"
        - "10/62399 - 21/04/2010 - Description - PG/C"
        """
        # Try to extract reference (at start, before first dash or space)
        ref_match = re.match(r"^([\d/]+(?:/\w+)?)", entry)
        reference = ref_match.group(1) if ref_match else "Unknown"
        
        # Try to extract date
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", entry)
        decision_date = date_match.group(1) if date_match else None
        
        # Try to extract decision status
        decision_status = None
        entry_upper = entry.upper()
        if "PG/C" in entry_upper:
            decision_status = "Permission Granted (Conditional)"
        elif "GRANTED" in entry_upper:
            decision_status = "Granted"
        elif "REFUSED" in entry_upper:
            decision_status = "Refused"
        elif "PENDING" in entry_upper:
            decision_status = "Pending"
        elif "WITHDRAWN" in entry_upper:
            decision_status = "Withdrawn"
        
        # Description is the remainder after removing ref, date, status
        description = entry
        # Remove the reference from start
        if ref_match:
            description = description[len(ref_match.group(0)):].strip(" -")
        # Remove date if found
        if date_match:
            description = description.replace(date_match.group(0), "").strip(" -")
        # Clean up status markers
        for marker in ["PG/C", "PG", "GRANTED", "REFUSED", "PENDING", "WITHDRAWN"]:
            description = re.sub(rf"\b{marker}\b", "", description, flags=re.IGNORECASE).strip(" -")
        
        description = re.sub(r"\s+", " ", description).strip(" -")
        
        # Determine if historic (older than 10 years from 2020 search date)
        is_historic = True
        if decision_date:
            try:
                year = int(decision_date.split("/")[2])
                is_historic = year < 2015
            except:
                pass
        
        note = "Historic entry" if is_historic else None
        
        return PlanningRegisterEntry(
            reference=reference,
            description=description if description else entry,
            decision_status=decision_status,
            decision_date=decision_date,
            is_historic=is_historic,
            note=note
        )
    
    def _structure_road_adoption(
        self,
        issues: list[str]
    ) -> list[RoadAdoptionFinding]:
        """
        Structure Road Adoption findings with neutral implications.
        """
        structured = []
        
        for issue in issues:
            # Skip non-road findings that may have been miscategorised
            if "public rights of way" in issue.lower():
                continue
            
            # Extract road name if present
            road_match = re.match(r"^([A-Z][A-Z\s]+(?:CLOSE|ROAD|LANE|STREET|AVENUE|WAY|DRIVE|COURT)?)\s*[-–—]", issue)
            road_name = road_match.group(1).strip() if road_match else "Road"
            
            # Determine implication
            implication = None
            if "not" in issue.lower() and ("adopted" in issue.lower() or "maintainable" in issue.lower()):
                implication = "Private maintenance obligations may apply"
            elif "adoption scheme" in issue.lower():
                implication = "Road may be adopted in future"
            
            structured.append(RoadAdoptionFinding(
                road_name=road_name,
                finding=issue,
                implication=implication,
                label=IssueLabel.MAINTENANCE_LIABILITY if implication else IssueLabel.INFORMATIONAL
            ))
        
        return structured
    
    def _structure_cil_findings(
        self,
        cil_entries: list[str]
    ) -> list[CILFinding]:
        """
        Structure CIL findings distinguishing regime from liability.
        """
        structured = []
        
        for entry in cil_entries:
            entry_lower = entry.lower()
            
            # Determine if this is regime or liability
            if "commenced" in entry_lower or "charging schedule" in entry_lower:
                finding_type = "regime"
                clarification = "CIL regime identified; liability depends on development history"
            elif "liability" in entry_lower or "amount" in entry_lower or "£" in entry:
                finding_type = "liability"
                clarification = "CIL liability may apply"
            else:
                finding_type = "regime"
                clarification = "CIL charging regime applies in this area"
            
            structured.append(CILFinding(
                finding_type=finding_type,
                description=entry,
                clarification=clarification,
                label=IssueLabel.FINANCIAL_LIABILITY if finding_type == "liability" else IssueLabel.INFORMATIONAL
            ))
        
        return structured
