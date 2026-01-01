"""
Deterministic compliance rules engine.

CRITICAL: This module contains ALL the business logic for compliance decisions.
The LLM is NEVER used for any decisions in this module.
All statuses are either:
1. Taken directly from provider data (source of truth)
2. Defaulted to REVIEW_REQUIRED if not provided
"""

from typing import Optional
from nomoros_ai.models.compliance import (
    Provider,
    CheckType,
    DeterministicStatus,
    ProviderStatusPayload,
    DeterministicComplianceState,
    GateEligibility,
)
from datetime import datetime


def compute_deterministic_state(
    matter_id: str,
    provider: Provider,
    check_type: CheckType,
    provider_status: Optional[ProviderStatusPayload],
    has_provider_reports: bool,
    has_sof_evidence: bool,
) -> DeterministicComplianceState:
    """
    Compute the deterministic compliance state from provider data.
    
    Rules:
    1. If provider_status contains id_aml_status/sof_status, use them
    2. If a status is missing but check_type expects it, default to REVIEW_REQUIRED
    3. If check_type doesn't include a check, status remains NOT_STARTED (not applicable)
    4. red_flags_found: use payload value if present, else (len(flags) > 0)
    5. missing_items lists clear reasons for incomplete compliance
    """
    id_aml_status = DeterministicStatus.NOT_STARTED
    sof_status = DeterministicStatus.NOT_STARTED
    red_flags_found = False
    provider_flags: list[str] = []
    missing_items: list[str] = []
    provider_reference_id: Optional[str] = None
    
    if provider_status:
        provider_reference_id = provider_status.provider_reference_id
        provider_flags = provider_status.flags.copy()
        
        if provider_status.red_flags_found is not None:
            red_flags_found = provider_status.red_flags_found
        else:
            red_flags_found = len(provider_flags) > 0
        
        if provider_status.id_aml_status is not None:
            id_aml_status = provider_status.id_aml_status
        
        if provider_status.sof_status is not None:
            sof_status = provider_status.sof_status
    
    requires_id_aml = check_type in (CheckType.ID_AML, CheckType.BOTH)
    requires_sof = check_type in (CheckType.SOF, CheckType.BOTH)
    
    if requires_id_aml:
        if id_aml_status == DeterministicStatus.NOT_STARTED:
            id_aml_status = DeterministicStatus.REVIEW_REQUIRED
        
        if not has_provider_reports and provider_status is None:
            missing_items.append(
                "Provider AML/ID report missing (or structured provider status not supplied)."
            )
        
        if id_aml_status != DeterministicStatus.PASSED:
            missing_items.append(f"ID/AML not cleared (status: {id_aml_status.value}).")
    
    if requires_sof:
        if sof_status == DeterministicStatus.NOT_STARTED:
            sof_status = DeterministicStatus.REVIEW_REQUIRED
        
        if not has_sof_evidence:
            missing_items.append("SoF evidence documents missing.")
        
        if sof_status != DeterministicStatus.PASSED:
            missing_items.append(f"Source of Funds not verified (status: {sof_status.value}).")
    
    if red_flags_found:
        missing_items.append("Provider reported red flags — solicitor review required.")
    
    return DeterministicComplianceState(
        matter_id=matter_id,
        provider=provider,
        provider_reference_id=provider_reference_id,
        id_aml_status=id_aml_status,
        sof_status=sof_status,
        red_flags_found=red_flags_found,
        provider_flags=provider_flags,
        missing_items=missing_items,
        computed_at=datetime.utcnow().isoformat() + "Z",
    )


def compute_gate_eligibility(
    state: DeterministicComplianceState,
    check_type: CheckType = CheckType.BOTH,
) -> GateEligibility:
    """
    Compute gate eligibility from deterministic state.
    
    Rules:
    - aml_eligible = (id_aml_status == PASSED) AND (red_flags_found == false)
      OR check_type doesn't require ID/AML (status is NOT_STARTED)
    - sof_eligible = (sof_status == PASSED) AND (red_flags_found == false)
      OR check_type doesn't require SoF (status is NOT_STARTED)
    - fully_eligible = aml_eligible AND sof_eligible (for applicable checks)
    
    When a check is not required (NOT_STARTED), it's considered eligible
    so that SOF-only or ID_AML-only flows can pass.
    """
    requires_id_aml = check_type in (CheckType.ID_AML, CheckType.BOTH)
    requires_sof = check_type in (CheckType.SOF, CheckType.BOTH)
    
    if requires_id_aml:
        aml_eligible = (
            state.id_aml_status == DeterministicStatus.PASSED
            and not state.red_flags_found
        )
    else:
        aml_eligible = True
    
    if requires_sof:
        sof_eligible = (
            state.sof_status == DeterministicStatus.PASSED
            and not state.red_flags_found
        )
    else:
        sof_eligible = True
    
    return GateEligibility(
        aml_eligible=aml_eligible,
        sof_eligible=sof_eligible,
        fully_eligible=aml_eligible and sof_eligible,
    )


def generate_fallback_summary(state: DeterministicComplianceState) -> str:
    """
    Generate a deterministic fallback summary when LLM is unavailable.
    This ensures the endpoint never fails due to LLM issues.
    """
    if (
        state.id_aml_status == DeterministicStatus.PASSED
        and state.sof_status == DeterministicStatus.PASSED
        and not state.red_flags_found
    ):
        return (
            "ID verified, AML cleared, SoF evidence received, "
            "no red flags reported by provider."
        )
    
    missing_notes = "; ".join(state.missing_items) if state.missing_items else "None"
    
    return (
        f"Compliance review required: "
        f"ID/AML status = {state.id_aml_status.value}, "
        f"SoF status = {state.sof_status.value}, "
        f"red flags = {state.red_flags_found}. "
        f"Missing/notes: {missing_notes}"
    )
