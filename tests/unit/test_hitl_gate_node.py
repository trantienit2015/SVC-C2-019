# SVC-C2-019 — Unit Tests: HITLGateNode (inner subgraph step 2, D6 interrupt())

from framework.schemas.agent_status import AgentStatus
from src.nodes import hitl_gate_node as hitl_gate_module
from src.nodes.hitl_gate_node import HITLGateNode


def _base_state(**overrides) -> dict:
    state = {
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-4",
        "onboarding_checklist": [{"task": "t1", "status": "pending"}],
        "new_hire_record": {"employee_id": "E-001"},
        "pii_masked_fields": ["my_number"],
    }
    state.update(overrides)
    return state


class TestHITLGateNode:
    def setup_method(self):
        self.node = HITLGateNode()

    def test_success_path_approved_feedback_keeps_checklist(self, monkeypatch):
        monkeypatch.setattr(
            hitl_gate_module,
            "interrupt",
            lambda payload: {"action": "approve", "approved_checklist": payload["draft"]["checklist"]},
        )

        result = self.node.execute(_base_state())

        assert result["status"] == AgentStatus.SUCCESS
        assert result["onboarding_checklist"] == [{"task": "t1", "status": "pending"}]
        assert result["hitl_feedback"]["action"] == "approve"
        assert result["hitl_draft"]["employee_id"] == "E-001"

    def test_edge_non_dict_feedback_falls_back_to_original_checklist(self, monkeypatch):
        monkeypatch.setattr(hitl_gate_module, "interrupt", lambda payload: "approve")

        original_checklist = [{"task": "t1", "status": "pending"}]
        result = self.node.execute(_base_state(onboarding_checklist=original_checklist))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["onboarding_checklist"] == original_checklist
        assert result["hitl_feedback"] == "approve"

    def test_corrected_feedback_replaces_checklist(self, monkeypatch):
        corrected = [{"task": "t1-corrected", "status": "pending"}]
        monkeypatch.setattr(
            hitl_gate_module,
            "interrupt",
            lambda payload: {"action": "correct", "approved_checklist": corrected},
        )

        result = self.node.execute(_base_state())

        assert result["status"] == AgentStatus.SUCCESS
        assert result["onboarding_checklist"] == corrected

    def test_edge_empty_checklist_skips_interrupt(self, monkeypatch):
        def _fail_if_called(payload):
            raise AssertionError("interrupt() must not be called when checklist is empty")

        monkeypatch.setattr(hitl_gate_module, "interrupt", _fail_if_called)

        result = self.node.execute(_base_state(onboarding_checklist=[]))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["onboarding_checklist"] == []
        assert "hitl_feedback" not in result


def _fail_if_interrupted(payload):
    raise AssertionError("interrupt() must not be called when no human can answer")


class TestHITLGateNodeDeferral:
    """The two skip conditions are independent — each is tested on its own,
    with the other one left at its gate-keeping value."""

    def test_hitl_not_allowed_defers_even_when_confirmation_required(self, monkeypatch):
        monkeypatch.setattr(hitl_gate_module, "interrupt", _fail_if_interrupted)
        node = HITLGateNode(confirmation_required=True)

        result = node.execute(_base_state(hitl_allowed=False))

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["onboarding_checklist"] == [{"task": "t1", "status": "pending", "hr_approval": "pending"}]
        assert "hitl_feedback" not in result

    def test_confirmation_not_required_defers_even_when_hitl_allowed(self, monkeypatch):
        monkeypatch.setattr(hitl_gate_module, "interrupt", _fail_if_interrupted)
        node = HITLGateNode(confirmation_required=False)

        result = node.execute(_base_state(hitl_allowed=True))

        assert result["status"] == AgentStatus.SUCCESS.value
        assert all(item["hr_approval"] == "pending" for item in result["onboarding_checklist"])
        assert "hitl_feedback" not in result

    def test_default_policy_still_interrupts(self, monkeypatch):
        calls = []
        monkeypatch.setattr(hitl_gate_module, "interrupt", lambda payload: calls.append(payload) or "approve")

        HITLGateNode().execute(_base_state(hitl_allowed=True))

        assert len(calls) == 1
