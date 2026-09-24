# SVC-C2-019 — Unit Tests: PIIGateNode (inner subgraph step 1, S-2)

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.pii_gate_node import PIIGateNode

VALID_NEW_HIRE = {
    "employee_id": "E-001",
    "role": "engineer",
    "location": "remote",
    "start_date": "2026-08-01",
}


def _base_state(user_input, **overrides) -> dict:
    state = {
        "user_input": user_input,
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-5",
    }
    state.update(overrides)
    return state


class TestPIIGateNode:
    def setup_method(self):
        self.node = PIIGateNode()

    def test_success_path_masks_my_number_and_other_pii(self):
        payload = json.dumps(
            {
                "new_hire": VALID_NEW_HIRE,
                "checklist": [{"task": "t1"}],
                "pii": {
                    "my_number": "123456789012",
                    "full_name": "Taro Yamada",
                    "phone_number": "090-0000-0000",
                },
            }
        )
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["my_number_detected"] is True
        assert set(result["pii_masked_fields"]) == {"my_number", "full_name", "phone_number"}
        assert result["new_hire_record"]["employee_id"] == "E-001"
        assert result["onboarding_checklist"] == [{"task": "t1"}]

    def test_no_pii_present_detects_nothing(self):
        payload = json.dumps({"new_hire": VALID_NEW_HIRE, "checklist": [], "pii": {}})
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["pii_masked_fields"] == []
        assert result["my_number_detected"] is False

    def test_malformed_input_returns_error_not_raise(self):
        result = self.node.execute(_base_state("not valid json"))

        assert result["status"] == AgentStatus.ERROR
        assert "error_log" in result and result["error_log"]

    def test_raw_pii_values_never_propagate(self):
        payload = json.dumps(
            {
                "new_hire": VALID_NEW_HIRE,
                "checklist": [],
                "pii": {"my_number": "999999999999", "bank_account": "1234567"},
            }
        )
        result = self.node.execute(_base_state(payload))

        # Only field NAMES propagate — never the raw masked values.
        assert "999999999999" not in json.dumps(result)
        assert "1234567" not in json.dumps(result)

    def test_missing_required_new_hire_field_rejects_before_downstream(self):
        """Re-validation guard: AgentBaseGraph's pre_process -> main edge is
        unconditional, so a rejected/malformed new_hire record from the outer
        ChecklistGenerateNode must not silently reach PII masking / HITL /
        provisioning just because it arrived via the raw user_input fallback."""
        payload = json.dumps({"new_hire": {"employee_id": "E-004"}, "checklist": [], "pii": {}})
        result = self.node.execute(_base_state(payload))

        assert result["status"] == AgentStatus.ERROR
        assert "error_log" in result and result["error_log"]
