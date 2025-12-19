"""
Title Register extraction service.

Extracts structured data from HM Land Registry Title Register documents.

Design notes:
- Currently uses regex-based extraction
- Structured to allow LLM integration later
- Falls back gracefully when patterns don't match
"""

import re
from typing import Optional

from nomoros_ai.models.title import (
    TitleRegisterExtraction,
    TitleClass,
    Proprietor,
    Restriction
)


class TitleExtractor:
    """
    Extracts structured data from Title Register OCR text.
    
    This class uses pattern matching to extract key fields from
    Title Register documents. It is designed to:
    
    1. Work deterministically with consistent output
    2. Handle OCR imperfections (spacing, line breaks)
    3. Be replaceable with LLM-based extraction later
    
    The extraction follows the standard Title Register structure:
    - Header: Title number, edition date
    - Section A: Property description
    - Section B: Proprietorship (owners, restrictions)
    - Section C: Charges
    """
    
    def extract(self, text: str) -> TitleRegisterExtraction:
        """
        Extract structured data from Title Register text.
        
        Args:
            text: OCR-extracted text from a Title Register
            
        Returns:
            TitleRegisterExtraction with populated fields
        """
        return TitleRegisterExtraction(
            title_number=self._extract_title_number(text),
            edition_date=self._extract_edition_date(text),
            property_description=self._extract_property_description(text),
            proprietors=self._extract_proprietors(text),
            title_class=self._extract_title_class(text),
            restrictions=self._extract_restrictions(text),
            charges_summary=self._extract_charges_summary(text)
        )
    
    def _extract_title_number(self, text: str) -> Optional[str]:
        """
        Extract the unique title number (e.g., BK480212).
        
        Title numbers follow the pattern: 1-3 letters followed by numbers.
        """
        # Pattern: Title number followed by alphanumeric code
        patterns = [
            r"Title\s+number\s+([A-Z]{1,3}\d+)",
            r"Title\s+number:\s*([A-Z]{1,3}\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None
    
    def _extract_edition_date(self, text: str) -> Optional[str]:
        """
        Extract the edition date of the register.
        
        This is the date the register was last updated.
        """
        patterns = [
            r"Edition\s+date\s+(\d{2}\.\d{2}\.\d{4})",
            r"Edition\s+date:\s*(\d{2}\.\d{2}\.\d{4})",
            r"Edition\s+date\s+(\d{2}/\d{2}/\d{4})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_property_description(self, text: str) -> Optional[str]:
        """
        Extract the property description from Section A.
        
        Section A contains the legal description of the property
        including its location and any rights benefiting it.
        """
        # Look for content between Property Register heading and next section
        pattern = r"Property\s+Register.*?(\(\d{2}\.\d{2}\.\d{4}\).*?(?:Way|Road|Street|Lane|Drive|Avenue|Close|Court|Gardens?|Place|Crescent|Square|Terrace|Grove|Hill|Park|Mews|Rise|View|Walk|Gate|Row|Yard|Passage|Alley|Circus|Green|Fields?|Meadow|Wood|Common)[^.]*\.[^.]*(?:RG|BS|SW|SE|NW|NE|EC|WC|E|W|N|S)\d+\s*\d*[A-Z]{0,2}\))"
        
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            # Clean up the description
            desc = match.group(1)
            desc = re.sub(r'\s+', ' ', desc).strip()
            return desc
        
        # Fallback: try to find any freehold/leasehold description
        pattern2 = r"(The\s+(?:Freehold|Leasehold)\s+land[^.]+\.[^.]*\))"
        match2 = re.search(pattern2, text, re.IGNORECASE | re.DOTALL)
        if match2:
            desc = match2.group(1)
            desc = re.sub(r'\s+', ' ', desc).strip()
            return desc
        
        return None
    
    def _extract_proprietors(self, text: str) -> list[Proprietor]:
        """
        Extract registered proprietors from Section B.
        
        Proprietors are the legal owners shown in the Proprietorship Register.
        """
        proprietors = []
        
        # Pattern for PROPRIETOR entries
        # Format: PROPRIETOR: NAME and NAME of ADDRESS
        pattern = r"PROPRIETOR:\s*([A-Z][A-Z\s]+(?:\s+and\s+[A-Z][A-Z\s]+)?)\s+of\s+([^.]+(?:\s+[A-Z]{1,2}\d+\s*\d*[A-Z]{0,2})?)"
        
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            names_str = match.group(1).strip()
            address = match.group(2).strip()
            
            # Handle multiple proprietors (NAME and NAME)
            if " and " in names_str.lower():
                names = re.split(r'\s+and\s+', names_str, flags=re.IGNORECASE)
                for name in names:
                    name = name.strip()
                    if name:
                        proprietors.append(Proprietor(
                            name=self._normalize_name(name),
                            address=address
                        ))
            else:
                proprietors.append(Proprietor(
                    name=self._normalize_name(names_str),
                    address=address
                ))
        
        return proprietors
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize a name to title case.
        
        Handles OCR artifacts and ALL CAPS formatting.
        """
        # Convert to title case
        name = name.strip()
        
        # Handle all-caps names from OCR
        if name.isupper():
            name = name.title()
        
        return name
    
    def _extract_title_class(self, text: str) -> TitleClass:
        """
        Extract the class of title from Section B.
        
        Title class indicates the quality of the title:
        - Absolute: Full guarantee from Land Registry
        - Possessory: Based on possession, not proof of title (HIGH RISK)
        - Good Leasehold: Similar to absolute for leasehold
        - Qualified: Subject to some defect
        """
        text_lower = text.lower()
        
        # Check for possessory title (high risk indicator)
        if "title possessory" in text_lower or "possessory title" in text_lower:
            return TitleClass.POSSESSORY
        
        # Check for qualified title
        if "title qualified" in text_lower or "qualified title" in text_lower:
            return TitleClass.QUALIFIED
        
        # Check for good leasehold
        if "good leasehold" in text_lower:
            return TitleClass.GOOD_LEASEHOLD
        
        # Check for absolute title (most common)
        if "title absolute" in text_lower or "absolute title" in text_lower:
            return TitleClass.ABSOLUTE
        
        # Check for freehold (implies absolute if not otherwise stated)
        if "freehold" in text_lower and "possessory" not in text_lower:
            return TitleClass.ABSOLUTE
        
        return TitleClass.UNKNOWN
    
    def _extract_restrictions(self, text: str) -> list[Restriction]:
        """
        Extract restrictions from Section B (Proprietorship Register).
        
        Restrictions limit how the property can be disposed of and
        typically require consent or certificate from a third party.
        
        Legal significance: Restrictions can delay or prevent
        transactions if not properly addressed.
        """
        restrictions = []
        
        # Pattern for RESTRICTION entries
        # Format: (DATE) RESTRICTION: full text until "apply to the disposition" or "have been complied with"
        # Date pattern allows for OCR artifacts like spaces: (22.08. 2018) or (22.08.2018)
        pattern = r"\((\d{2}\.\s*\d{2}\.\s*\d{4})\)\s*RESTRICTION:\s*(.*?(?:apply to the disposition|have been complied with)[^.]*\.)"
        
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            date = match.group(1)
            description = match.group(2).strip()
            
            # Clean up OCR artifacts
            description = re.sub(r'\s+', ' ', description)
            
            # Extract parties mentioned in the restriction
            parties = self._extract_parties_from_restriction(description)
            
            restrictions.append(Restriction(
                date_registered=date,
                description=description,
                parties_involved=parties if parties else None
            ))
        
        return restrictions
    
    def _extract_parties_from_restriction(self, text: str) -> list[str]:
        """
        Extract party names mentioned in a restriction.
        
        Parties are typically companies or individuals who must
        provide consent for dispositions.
        """
        parties = []
        
        # Look for company names (... Limited, ... Ltd, ... PLC)
        company_pattern = r"([A-Z][A-Za-z\s&]+(?:Limited|Ltd|PLC))"
        company_matches = re.findall(company_pattern, text)
        parties.extend([c.strip() for c in company_matches])
        
        return parties
    
    def _extract_charges_summary(self, text: str) -> Optional[str]:
        """
        Extract a summary of charges from Section C.
        
        Charges are typically mortgages or other financial
        interests registered against the property.
        """
        # Look for Charges Register section
        pattern = r"Charges\s+Register.*?(?:End of register|$)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        
        if match:
            charges_text = match.group(0)
            
            # Check if there are actual charges or just restrictive covenants
            if "charge" in charges_text.lower() and "dated" in charges_text.lower():
                # Extract the main charge details
                charge_pattern = r"(\(\d{2}\.\d{2}\.\d{4}\)[^.]+(?:charge|mortgage)[^.]+\.)"
                charge_match = re.search(charge_pattern, charges_text, re.IGNORECASE)
                if charge_match:
                    return charge_match.group(1).strip()
            
            # Check for restrictive covenants only
            if "restrictive covenants" in charges_text.lower():
                return "Subject to restrictive covenants (pre-existing)"
        
        return None
