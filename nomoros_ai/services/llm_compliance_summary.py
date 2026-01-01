"""
LLM-based compliance summary generation.

CRITICAL DESIGN PRINCIPLE:
- The LLM is used ONLY to generate human-readable draft summaries
- The LLM NEVER decides statuses, pass/fail, or gate eligibility
- All LLM outputs are clearly labeled as drafts requiring solicitor review
- If LLM fails, a deterministic fallback is used (endpoint never fails)
"""

import json
import logging
from typing import Optional
from datetime import datetime

from nomoros_ai.models.compliance import (
    DeterministicComplianceState,
    LLMDraftSummary,
)
from nomoros_ai.services.compliance_rules import generate_fallback_summary

logger = logging.getLogger(__name__)


def snippet_for_llm(text: str, max_chars: int = 1800) -> str:
    """
    Extract a relevant snippet from document text for LLM context.
    Prioritizes lines containing compliance-relevant keywords.
    """
    if not text:
        return ""
    
    keywords = [
        "pep", "sanctions", "adverse media", "match", "refer", "failed",
        "risk", "source of funds", "aml", "kyc", "verified", "passed",
        "identity", "document", "address", "bank", "income", "employment"
    ]
    
    lines = text.split("\n")
    priority_lines = []
    other_lines = []
    
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            priority_lines.append(line.strip())
        elif line.strip():
            other_lines.append(line.strip())
    
    combined = priority_lines + other_lines
    
    result = []
    char_count = 0
    for line in combined:
        if char_count + len(line) + 1 > max_chars:
            break
        result.append(line)
        char_count += len(line) + 1
    
    return "\n".join(result)


async def generate_llm_compliance_draft(
    state: DeterministicComplianceState,
    provider_snippet: str = "",
    sof_snippet: str = "",
) -> LLMDraftSummary:
    """
    Generate a draft compliance summary using Azure OpenAI.
    
    CRITICAL: The LLM is instructed to ONLY summarize the deterministic state.
    It must NOT decide pass/fail or set any statuses.
    
    If LLM fails for any reason, returns a deterministic fallback.
    """
    from nomoros_ai.config import settings as app_settings
    
    endpoint = app_settings.azure_openai_endpoint
    api_key = app_settings.openai_key
    deployment = app_settings.azure_openai_deployment
    api_version = app_settings.azure_openai_api_version
    
    if not endpoint or not api_key or not deployment:
        logger.warning("Azure OpenAI not configured, using fallback summary")
        return _create_fallback_draft(state)
    
    try:
        from openai import AzureOpenAI
        
        client = AzureOpenAI(
            azure_endpoint=str(endpoint),
            api_key=str(api_key),
            api_version=str(api_version),
        )
        
        system_prompt = """You are a compliance summary assistant for a legal conveyancing firm.
Your role is to generate a DRAFT summary for solicitor review.

CRITICAL RULES:
1. You must NEVER decide pass/fail status - that is already determined
2. You must NEVER infer compliance status from documents
3. You ONLY summarize the deterministic state provided to you
4. All your outputs are drafts requiring solicitor sign-off

Output a JSON object with these exact fields:
- compliance_summary_short: 1-2 sentence summary of current state
- key_flags: array of bullet points for any flags/concerns
- missing_evidence: array of bullet points for missing items
- confidence_note: 1 sentence about what needs solicitor attention"""

        state_summary = f"""DETERMINISTIC STATE (source of truth):
- Matter ID: {state.matter_id}
- Provider: {state.provider.value}
- ID/AML Status: {state.id_aml_status.value}
- SoF Status: {state.sof_status.value}
- Red Flags Found: {state.red_flags_found}
- Provider Flags: {', '.join(state.provider_flags) if state.provider_flags else 'None'}
- Missing Items: {', '.join(state.missing_items) if state.missing_items else 'None'}"""

        context_parts = [state_summary]
        if provider_snippet:
            context_parts.append(f"\nPROVIDER REPORT EXCERPT:\n{provider_snippet[:800]}")
        if sof_snippet:
            context_parts.append(f"\nSOF EVIDENCE EXCERPT:\n{sof_snippet[:800]}")
        
        user_message = "\n".join(context_parts)
        user_message += "\n\nGenerate a draft compliance summary JSON. Remember: you are summarizing the deterministic state above, NOT deciding anything."

        response = client.chat.completions.create(
            model=str(deployment),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        
        return LLMDraftSummary(
            draft_label="Draft — requires solicitor review",
            compliance_summary_short=parsed.get("compliance_summary_short", "Summary unavailable"),
            key_flags=parsed.get("key_flags", []),
            missing_evidence=parsed.get("missing_evidence", state.missing_items),
            confidence_note=parsed.get("confidence_note", "Requires solicitor review"),
            generated_at=datetime.utcnow().isoformat() + "Z",
            model_info=f"Azure OpenAI {deployment}",
            fallback_used=False,
        )
        
    except Exception as e:
        logger.error(f"LLM summary generation failed: {e}")
        return _create_fallback_draft(state)


def _create_fallback_draft(state: DeterministicComplianceState) -> LLMDraftSummary:
    """Create a deterministic fallback draft when LLM is unavailable."""
    fallback_text = generate_fallback_summary(state)
    
    return LLMDraftSummary(
        draft_label="Draft — requires solicitor review",
        compliance_summary_short=fallback_text,
        key_flags=state.provider_flags,
        missing_evidence=state.missing_items,
        confidence_note="Generated from deterministic state (LLM unavailable)",
        generated_at=datetime.utcnow().isoformat() + "Z",
        model_info="Deterministic fallback",
        fallback_used=True,
    )
