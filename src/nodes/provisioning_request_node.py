"""AgentCore Platform v1.0"""

from typing import Any, ClassVar
from uuid import uuid4

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

# Departments whose checklist tasks require a coordinated provisioning
# request (IT accounts/equipment, Facilities badges/kits). HR/Sales-Ops tasks
# are informational checklist items, not provisioning coordination targets —
# this agent coordinates provisioning requests, it does not own the
# provisioning systems themselves (docs/02_design.md scope boundary).
PROVISIONING_DEPARTMENTS = ("IT", "Facilities")


class ProvisioningRequestNode(FunctionNode):
    """Inner subgraph step 3: create cross-department IT/Facilities
    provisioning requests from the HR-approved checklist.

    Coordinates the request (creates a tracked record with a request_id);
    it does not call out to the provisioning systems themselves — those
    integrations are per-deployment adapters (docs/02_design.md).
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # Preservation-variant check: every provisioning request must keep
        # its request_id — a request without one cannot be tracked/reminded,
        # a control gap rather than just a formatting issue.
        for record in state.get("provisioning_requests", []):
            if not record.get("request_id"):
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": ["ProvisioningRequestNode: request missing request_id"],
                }
        return state

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        checklist = state.get("onboarding_checklist", [])
        new_hire = state.get("new_hire_record", {})
        employee_id = new_hire.get("employee_id")

        requests = [
            {
                "request_id": str(uuid4()),
                "task": item.get("task"),
                "department": item.get("department"),
                "employee_id": employee_id,
                # HR approval deferred (no human could answer the HITL gate):
                # record the request, but never as approved-and-requested.
                "status": "pending_hr_approval" if item.get("hr_approval") == "pending" else "requested",
            }
            for item in checklist
            if item.get("department") in PROVISIONING_DEPARTMENTS
        ]

        emit_trace_event(
            "provisioning_requests_dispatched",
            {
                "correlation_id": state.get("correlation_id"),
                "employee_id": employee_id,
                "request_count": len(requests),
            },
            state,
        )

        return {"provisioning_requests": requests, "status": AgentStatus.SUCCESS.value}
