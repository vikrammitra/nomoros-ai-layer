"""
Environmental Search extraction service.

Extracts structured data from UK Environmental Search reports using
deterministic text pattern matching. No LLM or ML used.

UK Environmental Search Structure (typical):
- Provider: Homecheck, Landmark, SearchFlow, etc.
- Section 1: Contamination Risk (EPA Part 2A)
  - Designated contaminated land
  - Landfill and waste sites
  - Potentially contaminative activities
  - Pollution incidents
- Section 2: Flood Risk
  - River flooding (EA zones)
  - Coastal flooding
  - Surface water flooding
- Section 3: Radon Risk
  - PHE radon data
  - Radon affected areas
- Section 4: Ground Stability
  - Man-made factors (mining, quarries)
  - Natural factors (clay shrinkage, landslip)
- Section 5: Other Factors
  - Environmental constraints
  - Energy infrastructure

Design principles:
- Prefer false negatives over false positives
- Only flag risks when clearly stated in text
- Leave as None/Unknown when uncertain
- All logic is deterministic and auditable
"""

import re
from nomoros_ai.models.search_environmental import EnvironmentalSearchExtraction


class EnvironmentalSearchExtractor:
    """
    Extractor for UK Environmental Search reports.
    
    Uses deterministic pattern matching to identify:
    - Flood risk levels
    - Contamination indicators
    - Historic industrial use
    - Mining and subsidence risk
    - Ground stability concerns
    
    All extraction is rule-based for legal defensibility.
    """
    
    def extract(self, ocr_text: str) -> EnvironmentalSearchExtraction:
        """
        Extract structured data from environmental search OCR text.
        
        Args:
            ocr_text: OCR-extracted text from environmental search PDF
            
        Returns:
            EnvironmentalSearchExtraction with populated fields
        """
        text_lower = ocr_text.lower()
        source_sections = []
        
        # Extract flood risk
        flood_risk = self._extract_flood_risk(text_lower)
        if flood_risk != "Unknown":
            source_sections.append("Flood Risk")
        
        # Extract contamination indicators
        contaminated_land = self._extract_contaminated_land(text_lower)
        if contaminated_land is not None:
            source_sections.append("Contamination Risk")
        
        # Extract historic industrial use
        historic_industrial = self._extract_historic_industrial(text_lower)
        if historic_industrial is not None:
            source_sections.append("Historic Land Use")
        
        # Extract mining/subsidence risk
        mining_subsidence = self._extract_mining_subsidence(text_lower)
        if mining_subsidence is not None:
            source_sections.append("Mining/Subsidence")
        
        # Extract radon risk
        radon_risk = self._extract_radon_risk(text_lower)
        if radon_risk is not None:
            source_sections.append("Radon")
        
        # Extract ground stability risk
        ground_stability = self._extract_ground_stability(text_lower)
        if ground_stability is not None:
            source_sections.append("Ground Stability")
        
        # Check for further action required
        further_action = self._extract_further_action(text_lower)
        if further_action is not None:
            source_sections.append("Recommendations")
        
        return EnvironmentalSearchExtraction(
            flood_risk=flood_risk,  # type: ignore[arg-type]
            contaminated_land=contaminated_land,
            historic_industrial_use=historic_industrial,
            mining_or_subsidence=mining_subsidence,
            radon_risk=radon_risk,
            ground_stability_risk=ground_stability,
            further_action_required=further_action,
            source_sections=source_sections
        )
    
    def _extract_flood_risk(self, text: str) -> str:
        """
        Extract flood risk level from environmental search.
        
        UK flood risk is typically categorized as:
        - Flood Zone 1: Low probability (<0.1% annual)
        - Flood Zone 2: Medium probability (0.1-1% annual)
        - Flood Zone 3: High probability (>1% annual)
        
        Also considers surface water flooding separately.
        """
        # Check for explicit "IDENTIFIED" markers (Homecheck/Landmark format)
        # These reports use "Flood Risk: IDENTIFIED" as a header
        if "flood risk" in text and "identified" in text:
            # Check for high flood indicators
            high_indicators = [
                "flood zone 3",
                "high probability",
                "significant flood risk",
                "high risk of flooding",
                "flood risk: high",
            ]
            for indicator in high_indicators:
                if indicator in text:
                    return "High"
            
            # Check for medium flood indicators
            medium_indicators = [
                "flood zone 2",
                "medium probability",
                "moderate flood risk",
                "flood risk: medium",
                "risk of flooding within 50m",
                "surface water flooding",
            ]
            for indicator in medium_indicators:
                if indicator in text:
                    return "Medium"
            
            # If flood is "identified" but no specific level, assume medium
            return "Medium"
        
        # Check for explicit no flood risk
        no_flood_indicators = [
            "flood zone 1",
            "low probability",
            "no flood risk",
            "flood risk: none",
            "flood risk: low",
            "not in a flood zone",
        ]
        for indicator in no_flood_indicators:
            if indicator in text:
                return "Low"
        
        # Check for "No" results in flood section tables
        # Homecheck format: "River Flooding  No  No"
        if re.search(r"river flooding\s+no\s+no", text):
            if re.search(r"surface water flooding\s+no\s+no", text):
                return "None"
        
        return "Unknown"
    
    def _extract_contaminated_land(self, text: str) -> bool | None:
        """
        Extract contaminated land status.
        
        Under EPA 1990 Part 2A, land is "contaminated" if pollutants
        cause significant harm or pollution of controlled waters.
        
        Environmental searches check:
        - Local Authority contaminated land registers
        - Historic landfill sites
        - Known pollution incidents
        
        IMPORTANT: Check "passed" status FIRST to avoid false positives
        """
        # PRIORITY CHECK: Homecheck/Landmark "PASSED" format
        # These reports show "PASSED" prominently when contamination risk is low
        if "contamination risk" in text:
            # Check for passed/clear indicators FIRST
            if "passed" in text and "professional opinion" in text:
                return False
            if "unlikely that the property would be designated" in text:
                return False
        
        # Check for explicit passed/clear indicators
        clear_indicators = [
            "contamination risk: pass",
            "contamination risk\npass",
            "passed this report",
            "contaminated land: no",
        ]
        for indicator in clear_indicators:
            if indicator in text:
                return False
        
        # Check table format: "Designated Contaminated Land  No  No  No"
        if "designated contaminated land" in text:
            # Look for "no" following the header
            idx = text.find("designated contaminated land")
            context = text[idx:idx+100]
            if "no" in context and "yes" not in context:
                return False
        
        # Check for positive contamination indicators
        positive_indicators = [
            "contaminated land identified",
            "part 2a designation",
            "contamination risk: fail",
            "contamination risk: refer",
            "contaminated land: yes",
            "remediation notice",
        ]
        for indicator in positive_indicators:
            if indicator in text:
                return True
        
        return None
    
    def _extract_historic_industrial(self, text: str) -> bool | None:
        """
        Extract historic industrial land use.
        
        Potentially contaminative activities include:
        - Factories and manufacturing
        - Petrol stations and garages
        - Dry cleaners
        - Metal works
        - Chemical storage
        
        Historic use may require Phase 1/2 environmental assessment.
        """
        positive_indicators = [
            "potentially contaminative activities",
            "historic industrial",
            "industrial land use",
            "factory",
            "petrol station",
            "garage",
            "works",
            "historic potentially contaminative",
        ]
        
        # Check if any positive indicator is followed by "yes" or "identified"
        for indicator in positive_indicators:
            if indicator in text:
                # Check context around the indicator
                idx = text.find(indicator)
                context = text[idx:idx+200]
                if "yes" in context or "identified" in context:
                    return True
        
        # Check Homecheck table format for potentially contaminative activities
        if re.search(r"potentially contaminative activities\s+no\s+yes", text):
            return True
        if re.search(r"potentially contaminative activities\s+no\s+no", text):
            return False
        
        return None
    
    def _extract_mining_subsidence(self, text: str) -> bool | None:
        """
        Extract mining and subsidence risk.
        
        UK areas affected by:
        - Coal mining (Coal Authority data)
        - Metal mining (tin, lead, copper)
        - Brine extraction
        
        NOTE: Natural ground stability (clay shrinkage, landslip) is
        handled separately in _extract_ground_stability, NOT here.
        This method only flags actual mining-related risks.
        
        CONSERVATIVE: Only return True for very explicit mining evidence.
        Prefer false negatives over false positives.
        """
        # Check for negative indicators FIRST (conservative approach)
        negative_indicators = [
            "not in a coal mining area",
            "no mining risk",
            "mining: no",
            "outside coal mining area",
        ]
        for indicator in negative_indicators:
            if indicator in text:
                return False
        
        # Check table format: "Man-Made Factors  No"
        if re.search(r"man-made factors\s+no", text):
            return False
        
        # Check for explicit mining indicators - must be very specific
        # These phrases clearly indicate mining presence
        positive_indicators = [
            "coal mining affected area",
            "within a coal mining area",
            "mining report recommended",
            "con29m recommended",
            "mine entries within",
            "mine shaft within",
            "brine extraction area",
        ]
        for indicator in positive_indicators:
            if indicator in text:
                return True
        
        # Check table format: "Man-Made Factors  Yes"
        if re.search(r"man-made factors\s+yes", text):
            return True
        
        # If no clear evidence, return None (unknown)
        # This is more conservative than returning False
        return None
    
    def _extract_radon_risk(self, text: str) -> bool | None:
        """
        Extract radon risk status.
        
        Radon is a naturally occurring radioactive gas.
        PHE designates areas where >1% of homes exceed action level.
        Properties in affected areas may need radon testing/mitigation.
        """
        # Check for explicit radon identification
        if "radon" in text:
            if "radon: identified" in text or "radon affected" in text:
                return True
            if "radon affected property" in text and "yes" in text:
                return True
            if "radon: no" in text or "not radon affected" in text:
                return False
        
        return None
    
    def _extract_ground_stability(self, text: str) -> bool | None:
        """
        Extract ground stability risk.
        
        Includes both:
        - Man-made factors (mining, quarries, infilled land)
        - Natural factors (clay shrinkage, landslip, running sand)
        """
        # Check section headers and results
        if "ground stability" in text:
            if "ground stability: identified" in text:
                return True
            
            # Check for natural/man-made factors
            if re.search(r"natural factors\s+yes", text):
                return True
            if re.search(r"man-made factors\s+yes", text):
                return True
            
            # Check for no factors
            if re.search(r"natural factors\s+no", text) and re.search(r"man-made factors\s+no", text):
                return False
        
        return None
    
    def _extract_further_action(self, text: str) -> bool | None:
        """
        Extract whether further action/investigation is recommended.
        
        Reports may recommend:
        - Phase 1 Environmental Assessment
        - Flood survey
        - Mining report
        - Radon testing
        """
        action_indicators = [
            "further investigation",
            "further enquiries",
            "further action required",
            "recommend",
            "advise",
            "should be obtained",
            "coal mining report",
            "radon test",
            "flood survey",
        ]
        
        for indicator in action_indicators:
            if indicator in text:
                # Check it's not in a "not required" context
                idx = text.find(indicator)
                pre_context = text[max(0, idx-50):idx]
                if "not " not in pre_context and "no " not in pre_context:
                    return True
        
        # Check for "REFER" status which means further review needed
        if "refer" in text and ("professional opinion" in text or "conveyancer guidance" in text):
            return True
        
        return None
