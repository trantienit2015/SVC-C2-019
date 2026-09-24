"""AgentCore Platform v1.0"""

# Inner subgraph step 1 — the core 番号法 (My Number Act) implementation
# (design decision: PIIGateNode is an independent S-2 node, not folded
# into ChecklistGenerateNode). Detects/masks My Number (特定個人情報) + 5 other
# PII field types BEFORE any downstream node (HITLGateNode, ProvisioningRequestNode,
# ReminderNode, StatusTrackNode, CompletionReportNode) ever sees them. Only
# field NAMES that were masked (never the raw values) are carried forward.

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.pii_masking_service import mask_pii

# Re-validated here, not just trusted from the outer ChecklistGenerateNode:
# AgentBaseGraph's pre_process -> main edge is UNCONDITIONAL (only main -> {route}
# is conditional), so a pre_process ERROR still dispatches into the inner
# subgraph via OnboardingWorkflowGraphNode.extract_input() falling back to the
# raw user_input (validated_input is only set on the ChecklistGenerateNode
# success path). Without this re-check a malformed/rejected new-hire record
# would silently sail through PII masking, HITL, and provisioning.
REQUIRED_NEW_HIRE_FIELDS = ("employee_id", "role", "location", "start_date")


class PIIGateNode(FunctionNode):
    """Inner subgraph step 1: mask My Number + 5 other PII field types.

    Runs inside the Cat 2 inner subgraph — receives only ``user_input``
    (JSON string set by the outer ChecklistGenerateNode), not the outer
    state. Discards the raw ``pii`` dict entirely after masking; only
    ``pii_masked_fields`` (field names) and ``my_number_detected`` (bool)
    propagate onward — the raw PII values never enter AgentState.
    """

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PIIGateNode: no valid onboarding payload in inner input"],
            }

        new_hire = payload.get("new_hire", {})
        checklist = payload.get("checklist", [])
        raw_pii = payload.get("pii", {})

        if not isinstance(new_hire, dict) or any(not new_hire.get(f) for f in REQUIRED_NEW_HIRE_FIELDS):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "PIIGateNode: new_hire record missing required field(s) — "
                    "upstream ChecklistGenerateNode rejection did not stop the pipeline"
                ],
            }

        masked_fields, my_number_detected = mask_pii(raw_pii)

        emit_trace_event(
            "pii_gate_masked",
            {
                "correlation_id": state.get("correlation_id"),
                "masked_field_count": len(masked_fields),
                "my_number_detected": my_number_detected,
            },
            state,
        )

        return {
            "new_hire_record": new_hire,
            "onboarding_checklist": checklist,
            "pii_masked_fields": masked_fields,
            "my_number_detected": my_number_detected,
            "status": AgentStatus.SUCCESS.value,
        }
