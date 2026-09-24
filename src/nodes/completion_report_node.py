"""AgentCore Platform v1.0"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event


class CompletionReportNode(FunctionNode):
    """Outer post_process: assemble the onboarding completion report.

    Reads the fields merged back from the inner subgraph (PII-masking
    outcome, provisioning requests, reminders, department status) and shapes
    the final ``formatted_output`` returned to the caller. Contains only
    counts/metadata — no raw PII (nothing raw PII-bearing is present in
    state by this point; PIIGateNode discarded it upstream).
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        new_hire = state.get("new_hire_record", {})
        checklist = state.get("onboarding_checklist", [])
        provisioning = state.get("provisioning_requests", [])
        reminders = state.get("reminders_sent", [])
        department_status = state.get("department_status", [])
        pii_masked_fields = state.get("pii_masked_fields", [])

        report = {
            "employee_id": new_hire.get("employee_id", ""),
            "checklist_task_count": len(checklist),
            "provisioning_request_count": len(provisioning),
            "reminders_sent_count": len(reminders),
            "departments_tracked": len(department_status),
            "pii_masked_field_count": len(pii_masked_fields),
        }

        emit_trace_event(
            "onboarding_completion_report_generated",
            {"correlation_id": state.get("correlation_id"), **report},
            state,
        )

        return {
            "completion_report": report,
            "formatted_output": report,
            "status": AgentStatus.SUCCESS.value,
        }
