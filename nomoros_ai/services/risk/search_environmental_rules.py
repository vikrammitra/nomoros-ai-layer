"""
Environmental Search risk detection rules.

Implements deterministic rule-based risk assessment for Environmental
Search data. All risk decisions are explicit and auditable.

Design principles:
- NO LLM/ML used for risk decisions
- Each rule is documented with legal rationale
- Severity levels are conservative
- Prefer false negatives over false positives

Risk categories (UK conveyancing context):
- Flood Risk: EA flood zones, surface water, coastal
- Contamination: EPA Part 2A, historic pollution
- Ground Stability: Mining, subsidence, clay shrinkage
- Radon: PHE radon affected areas

These risks may:
- Affect property value
- Impact insurance availability/cost
- Require remediation before purchase
- Influence lender decisions
"""

from nomoros_ai.models.search_environmental import (
    EnvironmentalSearchExtraction,
    EnvironmentalRisk,
    EnvironmentalRiskSummary
)


class EnvironmentalRiskAnalyzer:
    """
    Rule-based risk analyzer for Environmental Search data.
    
    Applies deterministic rules to identify environmental risks.
    Each rule is documented with legal context and recommendations.
    
    Risk triggers:
    - Flood risk High/Medium → High severity
    - Contaminated land → High severity  
    - Mining/subsidence → Medium severity
    - Historic industrial use → Medium severity
    - Further action required → Medium severity
    - Radon affected → Medium severity
    - Ground stability concerns → Medium severity
    """
    
    def analyze(self, extraction: EnvironmentalSearchExtraction) -> tuple[EnvironmentalRiskSummary, list[EnvironmentalRisk]]:
        """
        Analyze extracted environmental data for risks.
        
        Args:
            extraction: Structured data from environmental search extraction
            
        Returns:
            Tuple of (EnvironmentalRiskSummary, list of detailed risks)
        """
        risks: list[EnvironmentalRisk] = []
        
        # Apply each risk rule
        risks.extend(self._check_flood_risk(extraction))
        risks.extend(self._check_contamination(extraction))
        risks.extend(self._check_mining_subsidence(extraction))
        risks.extend(self._check_historic_industrial(extraction))
        risks.extend(self._check_radon(extraction))
        risks.extend(self._check_ground_stability(extraction))
        risks.extend(self._check_further_action(extraction))
        
        # Calculate severity breakdown
        high_count = sum(1 for r in risks if r.severity == "High")
        medium_count = sum(1 for r in risks if r.severity == "Medium")
        low_count = sum(1 for r in risks if r.severity == "Low")
        
        # Determine highest severity
        if high_count > 0:
            highest_severity = "High"
        elif medium_count > 0:
            highest_severity = "Medium"
        elif low_count > 0:
            highest_severity = "Low"
        else:
            highest_severity = "None"
        
        summary = EnvironmentalRiskSummary(
            category="Searches - Environmental",
            severity=highest_severity,
            severity_breakdown={"high": high_count, "medium": medium_count, "low": low_count},
            risk_count=len(risks),
            risks=[r.description for r in risks]
        )
        
        return summary, risks
    
    def _check_flood_risk(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Flood risk High or Medium → High severity.
        
        Legal context:
        Properties in Flood Zones 2/3 face:
        - Higher insurance premiums (or unavailability)
        - Potential difficulty obtaining mortgage
        - Risk of property damage and reduced value
        - Disclosure requirements on resale
        
        Environment Agency flood zones:
        - Zone 1: Low probability (<0.1% annual chance)
        - Zone 2: Medium probability (0.1-1% annual)
        - Zone 3: High probability (>1% annual)
        """
        risks = []
        
        if extraction.flood_risk == "High":
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="High",
                description="Property identified within high flood risk area (Flood Zone 3)",
                recommendation=(
                    "Obtain detailed flood report from Environment Agency. "
                    "Check buildings insurance availability and cost. "
                    "Consider flood resilience measures. "
                    "Confirm lender will accept property in flood zone."
                )
            ))
        elif extraction.flood_risk == "Medium":
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="High",
                description="Property identified within medium flood risk area (Flood Zone 2 or surface water)",
                recommendation=(
                    "Review flood history for the property. "
                    "Check buildings insurance terms and premiums. "
                    "Consider Flood Re scheme eligibility. "
                    "Request seller disclosure of any flood events."
                )
            ))
        
        return risks
    
    def _check_contamination(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Contaminated land identified → High severity.
        
        Legal context:
        Under EPA 1990 Part 2A:
        - Local authorities must maintain contaminated land register
        - Owners may be liable for remediation costs
        - "Polluter pays" principle applies, but current owner
          may be liable if polluter cannot be found
        - Remediation can be extremely expensive
        """
        risks = []
        
        if extraction.contaminated_land is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="High",
                description="Property on or near designated contaminated land",
                recommendation=(
                    "Obtain Phase 1 Environmental Site Assessment. "
                    "Review Local Authority contaminated land register. "
                    "Consider environmental indemnity insurance. "
                    "Assess potential remediation liability."
                )
            ))
        
        return risks
    
    def _check_mining_subsidence(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Mining or subsidence risk → Medium severity.
        
        Legal context:
        In coal mining areas:
        - Coal Authority maintains mining records
        - Subsidence damage may be covered by Coal Authority
        - Historic workings can cause delayed subsidence
        - Affects property value and insurability
        
        Other mining (tin, lead, etc.) not covered by Coal Authority.
        """
        risks = []
        
        if extraction.mining_or_subsidence is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="Medium",
                description="Mining or subsidence risk identified in area",
                recommendation=(
                    "Obtain Coal Authority mining report (CON29M). "
                    "Review for historic mine entries, shafts, or workings. "
                    "Check structural survey for subsidence evidence. "
                    "Confirm buildings insurance covers subsidence."
                )
            ))
        
        return risks
    
    def _check_historic_industrial(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Historic industrial use → Medium severity.
        
        Legal context:
        Potentially contaminative historic uses include:
        - Petrol stations and garages
        - Dry cleaners (solvent contamination)
        - Factories and manufacturing
        - Gas works
        - Metal plating/works
        
        May require Phase 1/2 environmental assessment before
        development or if contamination suspected.
        """
        risks = []
        
        if extraction.historic_industrial_use is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="Medium",
                description="Historic potentially contaminative land use identified nearby",
                recommendation=(
                    "Review nature of historic use and proximity to property. "
                    "Consider Phase 1 Environmental Assessment if concerned. "
                    "Check if any remediation has been undertaken. "
                    "May affect future development potential."
                )
            ))
        
        return risks
    
    def _check_radon(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Radon affected area → Medium severity.
        
        Legal context:
        Radon is a naturally occurring radioactive gas:
        - PHE designates "affected areas" where >1% homes exceed action level
        - Can accumulate in buildings, causing health risks
        - Testing is inexpensive and non-invasive
        - Mitigation (sumps, ventilation) is usually straightforward
        - Required disclosure on resale
        """
        risks = []
        
        if extraction.radon_risk is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="Medium",
                description="Property located in radon affected area",
                recommendation=(
                    "Arrange radon test (3-month measurement recommended). "
                    "If levels exceed 200 Bq/m³, remediation advised. "
                    "Check if property has existing radon protection. "
                    "Cost of mitigation typically £500-£1500."
                )
            ))
        
        return risks
    
    def _check_ground_stability(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Ground stability concerns → Medium severity.
        
        Legal context:
        Ground instability can result from:
        - Natural factors: clay shrinkage, landslip, running sand
        - Man-made factors: mining, quarrying, infilled land
        
        May affect:
        - Structural integrity of buildings
        - Insurance availability and cost
        - Future development/extension potential
        """
        risks = []
        
        if extraction.ground_stability_risk is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="Medium",
                description="Ground stability concerns identified (natural or man-made factors)",
                recommendation=(
                    "Review structural survey for signs of movement. "
                    "Check buildings insurance covers subsidence/heave. "
                    "Consider geotechnical assessment if major works planned. "
                    "Review historic maps for infilled land."
                )
            ))
        
        return risks
    
    def _check_further_action(self, extraction: EnvironmentalSearchExtraction) -> list[EnvironmentalRisk]:
        """
        Rule: Further action required → Medium severity.
        
        Legal context:
        Environmental search providers may recommend:
        - Further investigation (Phase 1 assessment)
        - Specialist reports (mining, flood)
        - Testing (radon, soil contamination)
        
        These recommendations should be followed up before
        exchange of contracts.
        """
        risks = []
        
        if extraction.further_action_required is True:
            risks.append(EnvironmentalRisk(
                category="Searches - Environmental",
                severity="Medium",
                description="Environmental search report recommends further investigation",
                recommendation=(
                    "Review specific recommendations in the search report. "
                    "Obtain any recommended specialist reports before exchange. "
                    "Consider cost and timing of further investigations. "
                    "Discuss implications with buyer/lender."
                )
            ))
        
        return risks
