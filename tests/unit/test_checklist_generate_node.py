# SVC-C2-019 — Unit Tests: ChecklistGenerateNode (outer pre_process)

import json

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from src.nodes.checklist_generate_node import ChecklistGenerateNode


def _base_state(user_input) -> dict:
    return {
        "user_input": user_input,
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-1",
    }


class TestChecklistGenerateNode:
    def setup_method(self):
        self.node = ChecklistGenerateNode()

    def test_success_path_generates_checklist(self):
        payload = json.dumps(
            {
                "new_hire": {
                    "employee_id": "E-001",
                    "role": "engineer",
                    "location": "remote",
                    "start_date": "2026-08-01",
                },
                "pii": {"my_number": "123456789012"},
            }
        )
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["new_hire_record"]["employee_id"] == "E-001"
        assert len(result["onboarding_checklist"]) > 0
        assert all(t["status"] == "pending" for t in result["onboarding_checklist"])

        validated = json.loads(result["validated_input"])
        assert validated["new_hire"]["employee_id"] == "E-001"
        assert validated["pii"] == {"my_number": "123456789012"}
        assert validated["checklist"] == result["onboarding_checklist"]

    def test_missing_required_field_rejects_record(self):
        payload = json.dumps(
            {
                "new_hire": {"employee_id": "E-002", "role": "engineer"},  # missing location/start_date
                "pii": {},
            }
        )
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.ERROR
        assert result["rejected_records"][0]["new_hire"]["employee_id"] == "E-002"
        assert "error_log" in result and result["error_log"]

    def test_malformed_input_returns_error_not_raise(self):
        result = self.node.execute(_base_state("not valid json"))

        assert result["status"] == AgentStatus.ERROR
        assert "error_log" in result and result["error_log"]

    def test_new_hire_not_a_dict_returns_error(self):
        payload = json.dumps({"new_hire": "oops", "pii": {}})
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.ERROR

    def test_s1_trust_gate_denies_insufficient_caller(self):
        state = _base_state(json.dumps({"new_hire": {}, "pii": {}}))
        state["caller_trust_level"] = TrustLevel.ANONYMOUS.value

        result = self.node(state)  # through __call__, not execute() directly

        assert result["status"] == AgentStatus.ERROR.value
        assert any("S-1 trust gate denied" in e for e in result["error_log"])

    def test_s1_trust_gate_allows_sufficient_caller(self):
        payload = json.dumps(
            {
                "new_hire": {
                    "employee_id": "E-003",
                    "role": "sales",
                    "location": "onsite",
                    "start_date": "2026-09-01",
                },
                "pii": {},
            }
        )
        state = _base_state(payload)
        state["caller_trust_level"] = TrustLevel.VERIFIED_EXTERNAL.value

        result = self.node(state)

        assert result["status"] == AgentStatus.SUCCESS
