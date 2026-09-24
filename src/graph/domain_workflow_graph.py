"""AgentCore Platform v1.0"""

# Inner graph for the Cat 2 HR onboarding workflow. Instantiated by
# OnboardingWorkflowGraphNode.get_subgraph() in graph.py — receives only the
# JSON-string user_input the outer ChecklistGenerateNode serialized, not the
# outer state directly (Cat 2 GraphNode boundary).

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from src.nodes.hitl_gate_node import HITLGateNode
from src.nodes.pii_gate_node import PIIGateNode
from src.nodes.provisioning_request_node import ProvisioningRequestNode
from src.nodes.reminder_node import ReminderNode
from src.nodes.status_track_node import StatusTrackNode
from src.schemas.state import State
from typing import Any


class OnboardingWorkflowGraph(BaseGraph):
    """Inner graph: PII gate -> HITL compliance gate (defers as pending when no human can answer) ->
    provisioning requests -> reminders -> status tracking."""

    @property
    def name(self) -> str:
        return "hr_onboarding_workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        pass

    def register_nodes(self) -> None:  # NOT super(); no initialize/finalize here
        self._nodes["pii_gate"] = PIIGateNode()
        hitl_cfg = (self.config or {}).get("hitl") or {}
        self._nodes["hitl_gate"] = HITLGateNode(
            confirmation_required=bool(hitl_cfg.get("confirmation_required", True)),
        )
        self._nodes["provisioning_request"] = ProvisioningRequestNode()
        self._nodes["reminder"] = ReminderNode()
        self._nodes["status_track"] = StatusTrackNode()

    def add_edges(self) -> None:
        self._sg.add_edge(START, "pii_gate")
        # Conditional: a malformed inner payload (PIIGateNode ERROR) must
        # short-circuit to END — the remaining steps are pure logic on
        # already-validated data and would otherwise silently overwrite the
        # ERROR status with SUCCESS on empty/malformed input.
        self._sg.add_conditional_edges("pii_gate", self.route)
        self._sg.add_edge("hitl_gate", "provisioning_request")
        self._sg.add_edge("provisioning_request", "reminder")
        self._sg.add_edge("reminder", "status_track")
        self._sg.add_edge("status_track", END)

    def route(self, state: AgentState) -> str:
        return END if state.get("status") == AgentStatus.ERROR.value else "hitl_gate"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "new_hire_record": state.get("new_hire_record", {}),
            "onboarding_checklist": state.get("onboarding_checklist", []),
            "pii_masked_fields": state.get("pii_masked_fields", []),
            "my_number_detected": state.get("my_number_detected", False),
            "provisioning_requests": state.get("provisioning_requests", []),
            "reminders_sent": state.get("reminders_sent", []),
            "department_status": state.get("department_status", []),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
