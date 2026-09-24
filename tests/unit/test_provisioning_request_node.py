# SVC-C2-019 — Unit Tests: ProvisioningRequestNode (inner subgraph step 3)

from framework.schemas.agent_status import AgentStatus
from src.nodes.provisioning_request_node import ProvisioningRequestNode


def _base_state(checklist, **overrides) -> dict:
    state = {
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-6",
        "onboarding_checklist": checklist,
        "new_hire_record": {"employee_id": "E-001"},
    }
    state.update(overrides)
    return state


class TestProvisioningRequestNode:
    def setup_method(self):
        self.node = ProvisioningRequestNode()

    def test_success_path_creates_requests_for_it_and_facilities_only(self):
        checklist = [
            {"task": "Provision corporate email account", "department": "IT"},
            {"task": "Issue employee ID badge", "department": "Facilities"},
            {"task": "Enroll in benefits orientation", "department": "HR"},
        ]
        result = self.node.execute(_base_state(checklist))

        assert result["status"] == AgentStatus.SUCCESS
        requests = result["provisioning_requests"]
        assert len(requests) == 2
        assert {r["department"] for r in requests} == {"IT", "Facilities"}
        assert all(r["request_id"] for r in requests)
        assert all(r["employee_id"] == "E-001" for r in requests)
        assert all(r["status"] == "requested" for r in requests)

    def test_edge_empty_checklist_produces_no_requests(self):
        result = self.node.execute(_base_state([]))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["provisioning_requests"] == []

    def test_extra_security_gate_output_passes_valid_state(self):
        state = {"provisioning_requests": [{"request_id": "r1"}]}
        result = self.node._extra_security_gate_output(state)

        assert result is state

    def test_extra_security_gate_output_rejects_missing_request_id(self):
        state = {"provisioning_requests": [{"task": "t1"}]}  # no request_id
        result = self.node._extra_security_gate_output(state)

        assert result["status"] == AgentStatus.ERROR
        assert "error_log" in result and result["error_log"]

    def test_deferred_hr_approval_records_pending_requests_not_requested(self):
        checklist = [
            {"task": "Issue laptop", "department": "IT", "hr_approval": "pending"},
            {"task": "Assign desk", "department": "Facilities", "hr_approval": "pending"},
        ]
        result = self.node.execute(_base_state(checklist))

        assert result["status"] == AgentStatus.SUCCESS.value
        assert [r["status"] for r in result["provisioning_requests"]] == ["pending_hr_approval"] * 2
