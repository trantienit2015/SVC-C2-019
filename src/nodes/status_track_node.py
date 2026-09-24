"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class StatusTrackNode(FunctionNode):
    """Inner subgraph step 5 (last): aggregate cross-department completion
    status from the provisioning requests."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        requests = state.get("provisioning_requests", [])

        by_department: dict[str, dict[str, Any]] = {}
        for r in requests:
            dept = r.get("department", "unknown")
            entry = by_department.setdefault(dept, {"department": dept, "total": 0, "completed": 0})
            entry["total"] += 1
            if r.get("status") == "completed":
                entry["completed"] += 1

        department_status = list(by_department.values())

        emit_trace_event(
            "department_status_tracked",
            {"correlation_id": state.get("correlation_id"), "department_count": len(department_status)},
            state,
        )

        return {"department_status": department_status, "status": AgentStatus.SUCCESS.value}
