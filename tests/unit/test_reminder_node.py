# SVC-C2-019 — Unit Tests: ReminderNode (inner subgraph step 4)

from framework.schemas.agent_status import AgentStatus
from src.nodes.reminder_node import ReminderNode


def _base_state(requests, **overrides) -> dict:
    state = {
        "node_history": [],
        "error_log": [],
        "execution_time": {},
        "correlation_id": "corr-7",
        "provisioning_requests": requests,
    }
    state.update(overrides)
    return state


class TestReminderNode:
    def setup_method(self):
        self.node = ReminderNode()

    def test_success_path_reminds_only_pending_requests(self):
        requests = [
            {"request_id": "r1", "department": "IT", "status": "requested"},
            {"request_id": "r2", "department": "Facilities", "status": "completed"},
        ]
        result = self.node.execute(_base_state(requests))

        assert result["status"] == AgentStatus.SUCCESS
        reminders = result["reminders_sent"]
        assert len(reminders) == 1
        assert reminders[0]["request_id"] == "r1"
        assert reminders[0]["channel"] == "department_reminder"

    def test_edge_no_provisioning_requests_produces_no_reminders(self):
        result = self.node.execute(_base_state([]))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["reminders_sent"] == []

    def test_all_completed_produces_no_reminders(self):
        requests = [{"request_id": "r1", "department": "IT", "status": "completed"}]
        result = self.node.execute(_base_state(requests))

        assert result["status"] == AgentStatus.SUCCESS
        assert result["reminders_sent"] == []
