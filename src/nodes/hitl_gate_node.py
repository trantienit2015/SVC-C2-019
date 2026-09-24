"""AgentCore Platform v1.0"""

# Inner subgraph step 2 — D6 HITL gate for HR compliance approval (design
# decision: HITLGateNode is an independent node, not inline logic folded
# into ProvisioningRequestNode). By default it interrupts for a human
# decision before any provisioning request is dispatched. It skips the
# interrupt on two independent conditions:
#   1. hitl_allowed is False — an automated caller (gateway / parent
#      GraphNode) cannot answer an interrupt (criterion #12);
#   2. hitl.confirmation_required is False — a deployment with no resume
#      channel (config/config.yaml).
# Neither path auto-approves: every checklist item is marked
# hr_approval="pending" and ProvisioningRequestNode records the matching
# requests as pending_hr_approval instead of requested.
# The framework owns pause/resume; this node only owns the trigger and
# merges the human's feedback into the checklist.
# Requires hitl.enabled:true + memory_enabled:true (config/config.yaml).

from typing import Any, ClassVar

from langgraph.types import interrupt

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class HITLGateNode(FunctionNode):
    """HR reviews/approves/modifies the onboarding checklist + PII-masking
    outcome before provisioning requests are coordinated.

    Suspends for human review unless no human can answer (see module
    comment) — never auto-approves. SLA timeout escalation to HR leadership
    is an ops-layer concern (queue/alerting outside this graph), documented
    in docs/02_design.md.
    """

    # S-1: inner subgraph node — trust authenticated once at the outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, confirmation_required: bool = True) -> None:
        super().__init__()
        # Static deployment policy set at construction — not per-invocation state.
        self._confirmation_required = confirmation_required

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        checklist = state.get("onboarding_checklist", [])
        new_hire = state.get("new_hire_record", {})

        # Nothing to review (e.g. upstream produced no checklist) — there is no
        # compliance decision for a human to make, so skip the interrupt rather
        # than pausing on an empty draft. Real invocations always populate the
        # checklist upstream (ChecklistGenerateNode), so this is a defensive
        # edge case, not a bypass of the approval requirement.
        if not checklist:
            emit_trace_event(
                "hitl_gate_skipped_empty_checklist", {"correlation_id": state.get("correlation_id")}, state
            )
            return {
                "onboarding_checklist": checklist,
                "status": AgentStatus.SUCCESS.value,
            }

        hitl_allowed = state.get("hitl_allowed", True)
        if not hitl_allowed or not self._confirmation_required:
            emit_trace_event(
                "hr_compliance_review_deferred",
                {
                    "correlation_id": state.get("correlation_id"),
                    "employee_id": new_hire.get("employee_id"),
                    "reason": "hitl_not_allowed" if not hitl_allowed else "confirmation_not_required",
                    "pending_task_count": len(checklist),
                },
                state,
            )
            return {
                "onboarding_checklist": [{**item, "hr_approval": "pending"} for item in checklist],
                "status": AgentStatus.SUCCESS.value,
            }

        draft = {
            "checklist": checklist,
            "employee_id": new_hire.get("employee_id"),
            "pii_masked_fields": state.get("pii_masked_fields", []),
        }

        # hitl_draft prevents re-computation on resume (framework contract).
        feedback = interrupt(
            {
                "draft": draft,
                "reason": "HR compliance approval required before provisioning dispatch",
            }
        )

        approved_checklist = feedback.get("approved_checklist", checklist) if isinstance(feedback, dict) else checklist

        emit_trace_event(
            "hr_compliance_review_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "employee_id": new_hire.get("employee_id"),
                "approved_task_count": len(approved_checklist),
            },
            state,
        )

        return {
            "hitl_draft": draft,
            "hitl_feedback": feedback,
            "onboarding_checklist": approved_checklist,
            "status": AgentStatus.SUCCESS.value,
        }
