"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class ReminderNode(FunctionNode):
    """Inner subgraph step 4: send reminders to departments with pending
    provisioning requests."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        requests = state.get("provisioning_requests", [])
        pending = [r for r in requests if r.get("status") != "completed"]

        reminders = [
            {
                "request_id": r.get("request_id"),
                "department": r.get("department"),
                "channel": "department_reminder",
            }
            for r in pending
        ]

        emit_trace_event(
            "onboarding_reminders_dispatched",
            {"correlation_id": state.get("correlation_id"), "reminder_count": len(reminders)},
            state,
        )

        return {"reminders_sent": reminders, "status": AgentStatus.SUCCESS.value}
