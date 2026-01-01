"""
Compliance ingest router for AML/ID and Source of Funds processing.

CRITICAL DESIGN PRINCIPLES:
1. Deterministic statuses are the ONLY source of truth
2. LLM is non-authoritative: summarizes but NEVER decides
3. Endpoint never fails due to LLM issues (fallback summary provided)
4. Returns structured JSON for UI consumption
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends

from nomoros_ai.auth import verify_api_key
from nomoros_ai.models.compliance import (
    Provider,
    CheckType,
    ProviderStatusPayload,
    ComplianceIngestResponse,
    ArtifactMetadata,
    StoredComplianceRecord,
)
from nomoros_ai.services.compliance_rules import (
    compute_deterministic_state,
    compute_gate_eligibility,
)
from nomoros_ai.services.llm_compliance_summary import (
    generate_llm_compliance_draft,
    snippet_for_llm,
)
from nomoros_ai.services.compliance_store import (
    save_compliance_record,
    get_compliance_record,
)
from nomoros_ai.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/compliance", tags=["Compliance"])


def validate_pdf(file: UploadFile) -> None:
    """Validate that uploaded file is a PDF."""
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only PDF files are accepted."
        )


async def extract_pdf_text(file: UploadFile) -> tuple[str, int, int]:
    """
    Extract text from PDF using Azure Document Intelligence.
    Returns (text, page_count, char_count).
    """
    from nomoros_ai.services.ocr.azure_doc_intelligence import AzureDocumentIntelligenceService
    
    endpoint = settings.azure_document_intelligence_endpoint
    api_key = settings.azure_document_intelligence_key
    
    if not endpoint or not api_key:
        logger.warning("Azure Document Intelligence not configured, skipping OCR")
        return "", 0, 0
    
    try:
        content = await file.read()
        await file.seek(0)
        
        service = AzureDocumentIntelligenceService(endpoint=endpoint, api_key=api_key)
        result = service.extract_text_from_pdf(content)
        
        if result.success:
            text = result.text_content or ""
            page_count = result.page_count or 0
            return text, page_count, len(text)
        else:
            logger.warning(f"OCR extraction failed for {file.filename}: {result.error_message}")
            return "", 0, 0
            
    except Exception as e:
        logger.error(f"Failed to extract text from {file.filename}: {e}")
        return "", 0, 0


@router.post("/ingest", response_model=ComplianceIngestResponse)
async def ingest_compliance_documents(
    matter_id: str = Form(...),
    provider: Provider = Form(...),
    check_type: CheckType = Form(...),
    provider_status_json: Optional[str] = Form(None),
    provider_reports: list[UploadFile] = File(default=[]),
    sof_evidence: list[UploadFile] = File(default=[]),
    _: str = Depends(verify_api_key),
):
    """
    Ingest compliance documents and compute deterministic compliance state.
    
    This endpoint:
    1. Validates and processes uploaded PDFs (AML/ID reports, SoF evidence)
    2. Computes DETERMINISTIC compliance state from provider data
    3. Generates an LLM draft summary (for solicitor review only)
    4. Never fails due to LLM issues (fallback summary provided)
    
    CRITICAL: The LLM NEVER decides statuses or gate eligibility.
    All compliance decisions are deterministic.
    """
    provider_status: Optional[ProviderStatusPayload] = None
    if provider_status_json:
        try:
            status_data = json.loads(provider_status_json)
            provider_status = ProviderStatusPayload.model_validate(status_data)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider_status_json: {e}"
            )
    
    for f in provider_reports:
        validate_pdf(f)
    for f in sof_evidence:
        validate_pdf(f)
    
    artifacts: list[ArtifactMetadata] = []
    provider_text_parts: list[str] = []
    sof_text_parts: list[str] = []
    
    for f in provider_reports:
        content = await f.read()
        await f.seek(0)
        
        text, page_count, char_count = await extract_pdf_text(f)
        provider_text_parts.append(text)
        
        artifacts.append(ArtifactMetadata(
            filename=f.filename or "unknown.pdf",
            content_type=f.content_type or "application/pdf",
            size_bytes=len(content),
            page_count=page_count if page_count > 0 else None,
            extracted_chars=char_count,
        ))
    
    for f in sof_evidence:
        content = await f.read()
        await f.seek(0)
        
        text, page_count, char_count = await extract_pdf_text(f)
        sof_text_parts.append(text)
        
        artifacts.append(ArtifactMetadata(
            filename=f.filename or "unknown.pdf",
            content_type=f.content_type or "application/pdf",
            size_bytes=len(content),
            page_count=page_count if page_count > 0 else None,
            extracted_chars=char_count,
        ))
    
    state = compute_deterministic_state(
        matter_id=matter_id,
        provider=provider,
        check_type=check_type,
        provider_status=provider_status,
        has_provider_reports=len(provider_reports) > 0,
        has_sof_evidence=len(sof_evidence) > 0,
    )
    
    eligibility = compute_gate_eligibility(state, check_type)
    
    provider_snippet = snippet_for_llm("\n\n".join(provider_text_parts))
    sof_snippet = snippet_for_llm("\n\n".join(sof_text_parts))
    
    llm_draft = await generate_llm_compliance_draft(
        state=state,
        provider_snippet=provider_snippet,
        sof_snippet=sof_snippet,
    )
    
    stored_record = StoredComplianceRecord(
        matter_id=matter_id,
        deterministic_state=state,
        gate_eligibility=eligibility,
        llm_draft=llm_draft,
        artifacts=artifacts,
    )
    save_compliance_record(stored_record)
    
    return ComplianceIngestResponse(
        success=True,
        matter_id=matter_id,
        deterministic_state=state,
        gate_eligibility=eligibility,
        llm_draft=llm_draft,
        fallback_summary_used=llm_draft.fallback_used,
        artifacts=artifacts,
        message="Compliance documents processed successfully",
    )


@router.get("/{matter_id}")
async def get_compliance_summary(
    matter_id: str,
    _: str = Depends(verify_api_key),
):
    """
    Retrieve the stored compliance summary for a matter.
    Returns the latest compliance state, eligibility, and draft summary.
    """
    record = get_compliance_record(matter_id)
    
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No compliance record found for matter {matter_id}"
        )
    
    return {
        "success": True,
        "matter_id": record.matter_id,
        "deterministic_state": record.deterministic_state,
        "gate_eligibility": record.gate_eligibility,
        "llm_draft": record.llm_draft,
        "artifacts": record.artifacts,
        "stored_at": record.stored_at,
    }
