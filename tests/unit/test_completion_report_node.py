# SVC-C2-019 — Unit Tests: CompletionReportNode (outer post_process)

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.completion_report_node import CompletionReportNode


def _base_state(**overrides) -> dict:
    state = {
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-2",
        "new_hire_record": {"employee_id": "E-001"},
        "onboarding_checklist": [{"task": "t1"}, {"task": "t2"}],
        "provisioning_requests": [{"request_id": "r1"}],
        "reminders_sent": [{"request_id": "r1"}],
        "department_status": [{"department": "IT", "total": 1, "completed": 0}],
        "pii_masked_fields": ["my_number", "full_name"],
    }
    state.update(overrides)
    return state


class TestCompletionReportNode:
    def setup_method(self):
        self.node = CompletionReportNode()

    def test_success_path_builds_report_counts(self):
        result = self.node.execute(_base_state())

        assert result["status"] == AgentStatus.SUCCESS
        report = result["completion_report"]
        assert report["employee_id"] == "E-001"
        assert report["checklist_task_count"] == 2
        assert report["provisioning_request_count"] == 1
        assert report["reminders_sent_count"] == 1
        assert report["departments_tracked"] == 1
        assert report["pii_masked_field_count"] == 2
        assert result["formatted_output"] == report

    def test_no_raw_pii_in_report(self):
        result = self.node.execute(_base_state())
        report = result["completion_report"]
        # Only counts/metadata — no raw PII values, no pii field names leaked verbatim.
        assert "my_number" not in str(report)
        assert "pii_masked_fields" not in report

    def test_edge_empty_upstream_fields_defaults_to_zero_counts(self):
        state = {
            "node_history": [],
            "error_log": [],
            "execution_time": {},
            "correlation_id": "corr-3",
        }
        result = self.node.execute(state)

        assert result["status"] == AgentStatus.SUCCESS
        report = result["completion_report"]
        assert report["employee_id"] == ""
        assert report["checklist_task_count"] == 0
        assert report["provisioning_request_count"] == 0
        assert report["reminders_sent_count"] == 0
        assert report["departments_tracked"] == 0
        assert report["pii_masked_field_count"] == 0

    def test_s1_trust_gate_denies_insufficient_caller(self):
        state = _base_state()
        state["caller_trust_level"] = TrustLevel.ANONYMOUS.value

        result = self.node(state)

        assert result["status"] == AgentStatus.ERROR.value
        assert any("S-1 trust gate denied" in e for e in result["error_log"])
