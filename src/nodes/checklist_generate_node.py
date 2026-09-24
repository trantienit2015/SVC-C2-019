"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus enum constants — never plain strings [A1]
#  - Never import from mediator/, api/, or other agents

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.checklist_service import generate_checklist

REQUIRED_NEW_HIRE_FIELDS = ("employee_id", "role", "location", "start_date")


class ChecklistGenerateNode(FunctionNode):
    """Outer pre_process: ingest the new-hire record + generate the
    role/location-specific onboarding checklist.

    Only the 4 non-PII new-hire fields (employee_id/role/location/start_date)
    are stored in ``new_hire_record``. Any raw PII the caller supplied
    (``pii`` in the payload) is forwarded, untouched, only inside
    ``validated_input`` for the inner subgraph's PIIGateNode (the very next
    node) to mask — it is never read or persisted as a named field here.
    """

    # S-1: outer boundary node — trust matches agent.yaml required_trust_level
    # (this agent receives HR-trigger payloads from an internal HR system).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_input = state.get("user_input", "")
        emit_trace_event(
            "onboarding_ingest_started",
            {"correlation_id": state.get("correlation_id")},
            state,
        )

        try:
            payload = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
        except (ValueError, TypeError):
            payload = None

        if not isinstance(payload, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ChecklistGenerateNode: user_input is not a valid onboarding payload"],
            }

        new_hire = payload.get("new_hire", {})
        pii = payload.get("pii", {})

        if not isinstance(new_hire, dict):
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ChecklistGenerateNode: new_hire record is missing or malformed"],
            }

        missing = [f for f in REQUIRED_NEW_HIRE_FIELDS if not new_hire.get(f)]
        if missing:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"ChecklistGenerateNode: new_hire missing required field(s): {missing}"],
                "rejected_records": [{"new_hire": new_hire, "reason": f"missing {missing}"}],
            }

        checklist = generate_checklist(new_hire["role"], new_hire["location"])

        validated_input = json.dumps({"new_hire": new_hire, "pii": pii, "checklist": checklist}, ensure_ascii=False)

        emit_trace_event(
            "onboarding_checklist_generated",
            {
                "correlation_id": state.get("correlation_id"),
                "employee_id": new_hire.get("employee_id"),
                "task_count": len(checklist),
            },
            state,
        )

        return {
            "new_hire_record": new_hire,
            "onboarding_checklist": checklist,
            "validated_input": validated_input,
            "status": AgentStatus.SUCCESS.value,
        }
