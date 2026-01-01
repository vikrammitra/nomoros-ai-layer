"""
Compliance document extraction service.

Extracts structured data from AML/ID and Source of Funds documents.
Uses deterministic regex-based extraction - no LLM for extraction decisions.
"""

import re
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class ComplianceDocType(str, Enum):
    AML_ID = "AML_ID"
    SOF = "SOF"


class ExtractedAMLID(BaseModel):
    """Extracted fields from AML/ID verification report."""
    provider: Optional[str] = None
    provider_reference: Optional[str] = None
    verification_date: Optional[str] = None
    deterministic_status: Optional[str] = None
    applicant_name: Optional[str] = None
    applicant_dob: Optional[str] = None
    applicant_address: Optional[str] = None
    matter_id: Optional[str] = None
    property_address: Optional[str] = None
    pep_screening: Optional[str] = None
    sanctions_screening: Optional[str] = None
    adverse_media: Optional[str] = None
    provider_flags: list[str] = []


class ExtractedSOF(BaseModel):
    """Extracted fields from Source of Funds evidence pack."""
    sof_reference: Optional[str] = None
    pack_date: Optional[str] = None
    deterministic_status: Optional[str] = None
    primary_source: Optional[str] = None
    secondary_source: Optional[str] = None
    purchase_price: Optional[str] = None
    deposit_amount: Optional[str] = None
    account_used: Optional[str] = None
    salary_credits: list[str] = []
    large_transfers: list[str] = []
    unusual_transactions: list[str] = []
    review_points: list[str] = []


class ComplianceRisk(BaseModel):
    """Individual risk finding from compliance document."""
    category: str
    severity: str  # HIGH, MEDIUM, LOW
    description: str
    evidence: Optional[str] = None


class ComplianceExtractionResult(BaseModel):
    """Result of compliance document extraction and risk analysis."""
    doc_type: ComplianceDocType
    aml_id: Optional[ExtractedAMLID] = None
    sof: Optional[ExtractedSOF] = None
    risks: list[ComplianceRisk] = []
    risk_summary: str = ""


class ComplianceExtractor:
    """Extracts structured data from compliance documents."""
    
    def extract_aml_id(self, text: str) -> ExtractedAMLID:
        """Extract fields from AML/ID verification report."""
        result = ExtractedAMLID()
        text_lower = text.lower()
        
        if "thirdfort" in text_lower:
            result.provider = "Thirdfort"
        elif "credas" in text_lower:
            result.provider = "Credas"
        
        ref_match = re.search(r'(?:provider reference|reference)[:\s]+([A-Z0-9\-]+)', text, re.IGNORECASE)
        if ref_match:
            result.provider_reference = ref_match.group(1)
        
        date_match = re.search(r'(?:verification date)[:\s]+(\d{4}-\d{2}-\d{2}[^\n]*)', text, re.IGNORECASE)
        if date_match:
            result.verification_date = date_match.group(1).strip()
        
        status_match = re.search(r'(?:deterministic status[^\n]*)\n?\s*(PASSED|FAILED|REVIEW_REQUIRED|PENDING)', text, re.IGNORECASE)
        if status_match:
            result.deterministic_status = status_match.group(1).upper()
        
        name_match = re.search(r'(?:full name|applicant name)[:\s]+([A-Za-z\s]+?)(?:\n|DOB|$)', text, re.IGNORECASE)
        if name_match:
            result.applicant_name = name_match.group(1).strip()
        
        dob_match = re.search(r'(?:DOB|date of birth)[:\s]+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if dob_match:
            result.applicant_dob = dob_match.group(1)
        
        matter_match = re.search(r'(?:matter id)[:\s]+([A-Z0-9\-]+)', text, re.IGNORECASE)
        if matter_match:
            result.matter_id = matter_match.group(1)
        
        pep_match = re.search(r'(?:pep screening)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if pep_match:
            result.pep_screening = pep_match.group(1).strip()
        
        sanctions_match = re.search(r'(?:sanctions screening)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if sanctions_match:
            result.sanctions_screening = sanctions_match.group(1).strip()
        
        adverse_match = re.search(r'(?:adverse media)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if adverse_match:
            result.adverse_media = adverse_match.group(1).strip()
        
        flags = re.findall(r'-\s*(Potential PEP match|Adverse media indicator|[^\n]+flag[^\n]*)', text, re.IGNORECASE)
        result.provider_flags = [f.strip() for f in flags]
        
        return result
    
    def extract_sof(self, text: str) -> ExtractedSOF:
        """Extract fields from Source of Funds evidence pack."""
        result = ExtractedSOF()
        
        ref_match = re.search(r'(?:sof reference|reference)[:\s]+([A-Z0-9\-]+)', text, re.IGNORECASE)
        if ref_match:
            result.sof_reference = ref_match.group(1)
        
        date_match = re.search(r'(?:pack date)[:\s]+(\d{4}-\d{2}-\d{2}[^\n]*)', text, re.IGNORECASE)
        if date_match:
            result.pack_date = date_match.group(1).strip()
        
        status_match = re.search(r'(?:deterministic status[^\n]*)\n?\s*(PASSED|FAILED|REVIEW_REQUIRED|PENDING)', text, re.IGNORECASE)
        if status_match:
            result.deterministic_status = status_match.group(1).upper()
        
        primary_match = re.search(r'(?:primary source)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if primary_match:
            result.primary_source = primary_match.group(1).strip()
        
        secondary_match = re.search(r'(?:secondary source)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if secondary_match:
            result.secondary_source = secondary_match.group(1).strip()
        
        price_match = re.search(r'(?:purchase price)[^\n]*?(?:GBP|£)\s*([\d,]+)', text, re.IGNORECASE)
        if price_match:
            result.purchase_price = f"GBP {price_match.group(1)}"
        
        deposit_match = re.search(r'(?:deposit amount)[^\n]*?(?:GBP|£)\s*([\d,]+)', text, re.IGNORECASE)
        if deposit_match:
            result.deposit_amount = f"GBP {deposit_match.group(1)}"
        
        account_match = re.search(r'(?:account used)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if account_match:
            result.account_used = account_match.group(1).strip()
        
        salary_matches = re.findall(r'(\d{4}-\d{2}-\d{2})\s+([A-Z\s]+SALARY[^\n]*?)([\d,]+\.?\d*)', text, re.IGNORECASE)
        result.salary_credits = [f"{m[0]}: {m[1].strip()} - GBP {m[2]}" for m in salary_matches]
        
        transfer_matches = re.findall(r'(\d{4}-\d{2}-\d{2})\s+([^\n]*TRANSFER[^\n]*?)([\d,]+\.?\d*)', text, re.IGNORECASE)
        large_transfers = []
        for m in transfer_matches:
            try:
                amount = float(m[2].replace(',', ''))
                if amount >= 5000:
                    large_transfers.append(f"{m[0]}: {m[1].strip()} - GBP {m[2]}")
            except ValueError:
                pass
        result.large_transfers = large_transfers
        
        review_matches = re.findall(r'-\s+([^\n]+(?:review|risk|unusual|inconsistent)[^\n]*)', text, re.IGNORECASE)
        result.review_points = [r.strip() for r in review_matches]
        
        return result


class ComplianceRiskAnalyzer:
    """Deterministic risk analysis for compliance documents."""
    
    def analyze_aml_id(self, extracted: ExtractedAMLID) -> list[ComplianceRisk]:
        """Analyze AML/ID extraction for risks."""
        risks = []
        
        if extracted.deterministic_status == "FAILED":
            risks.append(ComplianceRisk(
                category="AML/ID Status",
                severity="HIGH",
                description="AML/ID verification FAILED - transaction cannot proceed",
                evidence=f"Status: {extracted.deterministic_status}"
            ))
        elif extracted.deterministic_status == "REVIEW_REQUIRED":
            risks.append(ComplianceRisk(
                category="AML/ID Status",
                severity="MEDIUM",
                description="AML/ID verification requires manual review before proceeding",
                evidence=f"Status: {extracted.deterministic_status}"
            ))
        
        if extracted.pep_screening and "match" in extracted.pep_screening.lower():
            risks.append(ComplianceRisk(
                category="PEP Screening",
                severity="HIGH",
                description="Potential Politically Exposed Person (PEP) match detected",
                evidence=extracted.pep_screening
            ))
        
        if extracted.sanctions_screening and "match" in extracted.sanctions_screening.lower() and "no match" not in extracted.sanctions_screening.lower():
            risks.append(ComplianceRisk(
                category="Sanctions",
                severity="HIGH",
                description="Potential sanctions list match detected - immediate review required",
                evidence=extracted.sanctions_screening
            ))
        
        if extracted.adverse_media and "present" in extracted.adverse_media.lower():
            risks.append(ComplianceRisk(
                category="Adverse Media",
                severity="MEDIUM",
                description="Adverse media indicators found - review news/media coverage",
                evidence=extracted.adverse_media
            ))
        
        for flag in extracted.provider_flags:
            if "pep" in flag.lower():
                if not any(r.category == "PEP Screening" for r in risks):
                    risks.append(ComplianceRisk(
                        category="Provider Flag",
                        severity="HIGH",
                        description="Provider flagged potential PEP match",
                        evidence=flag
                    ))
            elif "adverse" in flag.lower():
                if not any(r.category == "Adverse Media" for r in risks):
                    risks.append(ComplianceRisk(
                        category="Provider Flag",
                        severity="MEDIUM",
                        description="Provider flagged adverse media indicator",
                        evidence=flag
                    ))
        
        return risks
    
    def analyze_sof(self, extracted: ExtractedSOF) -> list[ComplianceRisk]:
        """Analyze Source of Funds extraction for risks."""
        risks = []
        
        if extracted.deterministic_status == "FAILED":
            risks.append(ComplianceRisk(
                category="SOF Status",
                severity="HIGH",
                description="Source of Funds verification FAILED - funds origin not verified",
                evidence=f"Status: {extracted.deterministic_status}"
            ))
        elif extracted.deterministic_status == "REVIEW_REQUIRED":
            risks.append(ComplianceRisk(
                category="SOF Status",
                severity="MEDIUM",
                description="Source of Funds requires manual review",
                evidence=f"Status: {extracted.deterministic_status}"
            ))
        
        if extracted.large_transfers:
            for transfer in extracted.large_transfers:
                if "solicitor" not in transfer.lower():
                    risks.append(ComplianceRisk(
                        category="Large Transfer",
                        severity="LOW",
                        description="Large transfer detected - verify source",
                        evidence=transfer
                    ))
        
        if not extracted.salary_credits and extracted.primary_source and "salary" in extracted.primary_source.lower():
            risks.append(ComplianceRisk(
                category="Income Verification",
                severity="MEDIUM",
                description="Primary source declared as salary but no salary credits found in statement",
                evidence=f"Declared: {extracted.primary_source}"
            ))
        
        for point in extracted.review_points:
            if "unusual" in point.lower() or "inconsistent" in point.lower():
                risks.append(ComplianceRisk(
                    category="Review Point",
                    severity="MEDIUM",
                    description=point,
                    evidence=None
                ))
        
        return risks
    
    def get_risk_summary(self, risks: list[ComplianceRisk]) -> str:
        """Generate a summary of the risk findings."""
        if not risks:
            return "No compliance risks identified."
        
        high_count = sum(1 for r in risks if r.severity == "HIGH")
        medium_count = sum(1 for r in risks if r.severity == "MEDIUM")
        low_count = sum(1 for r in risks if r.severity == "LOW")
        
        parts = []
        if high_count > 0:
            parts.append(f"{high_count} HIGH")
        if medium_count > 0:
            parts.append(f"{medium_count} MEDIUM")
        if low_count > 0:
            parts.append(f"{low_count} LOW")
        
        return f"Found {len(risks)} risk(s): {', '.join(parts)}. Review required before proceeding."


def extract_and_analyze_compliance(text: str, doc_type: str) -> ComplianceExtractionResult:
    """
    Main entry point for compliance document extraction and risk analysis.
    
    Args:
        text: OCR-extracted text from compliance document
        doc_type: Document type ("COMPLIANCE_AML_ID" or "COMPLIANCE_SOF")
    
    Returns:
        ComplianceExtractionResult with extracted data and risks
    """
    extractor = ComplianceExtractor()
    analyzer = ComplianceRiskAnalyzer()
    
    if doc_type == "COMPLIANCE_AML_ID":
        aml_id = extractor.extract_aml_id(text)
        risks = analyzer.analyze_aml_id(aml_id)
        return ComplianceExtractionResult(
            doc_type=ComplianceDocType.AML_ID,
            aml_id=aml_id,
            risks=risks,
            risk_summary=analyzer.get_risk_summary(risks)
        )
    else:
        sof = extractor.extract_sof(text)
        risks = analyzer.analyze_sof(sof)
        return ComplianceExtractionResult(
            doc_type=ComplianceDocType.SOF,
            sof=sof,
            risks=risks,
            risk_summary=analyzer.get_risk_summary(risks)
        )
