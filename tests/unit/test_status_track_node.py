# SVC-C2-019 — Unit Tests: StatusTrackNode (inner subgraph step 5, last)

from framework.schemas.agent_status import AgentStatus
from src.nodes.status_track_node import StatusTrackNode


def _base_state(requests, **overrides) -> dict:
    state = {
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-8",
        "provisioning_requests": requests,
    }
    state.update(overrides)
    return state


class TestStatusTrackNode:
    def setup_method(self):
        self.node = StatusTrackNode()

    def test_success_path_aggregates_by_department(self):
        requests = [
            {"request_id": "r1", "department": "IT", "status": "completed"},
            {"request_id": "r2", "department": "IT", "status": "requested"},
            {"request_id": "r3", "department": "Facilities", "status": "completed"},
        ]
        result = self.node.execute(_base_state(requests))

        assert result["status"] == AgentStatus.SUCCESS
        by_dept = {d["department"]: d for d in result["department_status"]}
        assert by_dept["IT"] == {"department": "IT", "total": 2, "completed": 1}
        assert by_dept["Facilities"] == {"department": "Facilities", "total": 1, "completed": 1}

    def test_edge_empty_requests_produces_no_department_status(self):
        result = self.node.execute(_base_state([]))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["department_status"] == []

    def test_missing_department_field_grouped_as_unknown(self):
        requests = [{"request_id": "r1", "status": "requested"}]
        result = self.node.execute(_base_state(requests))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["department_status"] == [{"department": "unknown", "total": 1, "completed": 0}]
