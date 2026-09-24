"""AgentCore Platform v1.0"""

# Cat 2 — SVC-C2-019 HR Onboarding Process Orchestration Agent. Outer graph
# (this file) = AgentBaseGraph fixed 5-node backbone; the domain pipeline
# (PII gate -> HITL compliance gate -> provisioning -> reminders -> status
# tracking) lives in the inner subgraph (src/graph/domain_workflow_graph.py),
# wrapped by OnboardingWorkflowGraphNode in the `main` slot. See
# the project standard for the full contract.
#
# HITL: `hitl.enabled: true` in config/config.yaml. The inner HITLGateNode
# calls interrupt() for HR compliance approval unless hitl_allowed is False
# or hitl.confirmation_required is False (then it defers approval as pending
# instead); propagate_hitl=True below surfaces the interrupt to the OUTER
# graph so the whole agent pauses (AWAITING_HUMAN) rather than only the
# inner subgraph. The outer `hitl` block is forwarded to the inner graph
# via _parent_config().

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.nodes.checklist_generate_node import ChecklistGenerateNode
from src.nodes.completion_report_node import CompletionReportNode
from src.schemas.state import State


class OnboardingWorkflowGraphNode(GraphNode):
    """Wraps the inner PII-gate -> HITL-gate -> provisioning -> reminder ->
    status-track workflow; assigned to the outer `main` slot."""

    # S-1: outer main-slot wrapper — first node in the outer backbone to
    # receive caller input; matches agent.yaml required_trust_level and the
    # sibling outer nodes (ChecklistGenerateNode / CompletionReportNode).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # "propagate": re-raise inner graph exceptions as SubgraphError (fail fast).
    error_strategy: ClassVar[str] = "propagate"

    # True: surface the inner HITLGateNode's interrupt() to the outer graph
    # caller — the whole agent pauses (AWAITING_HUMAN), not just the inner
    # subgraph. Requires hitl.enabled: true in agent.yaml (present).
    propagate_hitl: ClassVar[bool] = True

    def __init__(self, hitl: dict[str, Any] | None = None) -> None:
        super().__init__()
        # Outer `hitl` config block (static, set at construction) — forwarded
        # to the inner graph so hitl.confirmation_required reaches HITLGateNode.
        self._hitl = dict(hitl or {})
        # Cache the compiled inner subgraph (with its own checkpointer) so the
        # same checkpoint is reused across an invoke() -> resume() cycle — a
        # fresh saver each call would lose the paused HITL session.
        self._subgraph = self._build_subgraph()

    def _build_subgraph(self) -> Any:
        from langgraph.checkpoint.memory import InMemorySaver

        from src.graph.domain_workflow_graph import OnboardingWorkflowGraph

        sg = OnboardingWorkflowGraph(config=self._parent_config())
        sg.compile(checkpointer=InMemorySaver())
        return sg

    def get_subgraph(self) -> Any:
        return self._subgraph

    def extract_input(self, state: AgentState) -> str:
        # S-4: emit_trace_event runs here — inside GraphNode.execute() — since
        # this GraphNode subclass does not (and must not) override execute().
        emit_trace_event(
            "onboarding_workflow_dispatched",
            {"correlation_id": state.get("correlation_id")},
            state,
        )
        return str(state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        emit_trace_event(
            "onboarding_workflow_completed",
            {
                "correlation_id": state.get("correlation_id"),
                "my_number_detected": sub_result.get("my_number_detected"),
                "status": sub_result.get("status"),
            },
            state,
        )
        return {
            "new_hire_record": sub_result.get("new_hire_record", state.get("new_hire_record", {})),
            "onboarding_checklist": sub_result.get("onboarding_checklist", state.get("onboarding_checklist", [])),
            "pii_masked_fields": sub_result.get("pii_masked_fields", []),
            "my_number_detected": sub_result.get("my_number_detected", False),
            "provisioning_requests": sub_result.get("provisioning_requests", []),
            "reminders_sent": sub_result.get("reminders_sent", []),
            "department_status": sub_result.get("department_status", []),
            "result": sub_result.get("output"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {
            # Mandatory for the inner subgraph too: HITLGateNode's interrupt()
            # requires a thread-scoped checkpointer to suspend/resume (ADR-016 D5).
            "memory_enabled": True,
            "hitl": {"enabled": True, "max_hitl": 8, **self._hitl},
        }

    def _handle_call_error(self, subgraph: Any, e: Exception, state: AgentState) -> dict[str, Any]:
        # LangGraph sentinel exceptions (GraphInterrupt et al.) must bubble up
        # to the runtime unmodified — never wrapped into SubgraphError.
        from langgraph.errors import GraphBubbleUp

        if isinstance(e, GraphBubbleUp) or "interrupt" in type(e).__name__.lower():
            raise e
        return cast(dict[str, Any], super()._handle_call_error(subgraph, e, state))


class HROnboardingOrchestrationGraph(AgentBaseGraph):
    """SVC-C2-019 — outer graph. Backbone: initialize -> pre_process -> main
    -> post_process -> finalize."""

    def __init__(self, config: dict[str, Any] | None = None):
        # HITL (D6 interrupt(), HR compliance approval) requires
        # memory_enabled/hitl.enabled on the OUTER graph too — BaseGraph.invoke()
        # only builds the thread-scoped checkpointer config when one of these is
        # set, and the outer graph is always compiled with a checkpointer (see
        # src/api/server.py, tests). These defaults mirror config/agent.yaml so a
        # bare Graph() (e.g. in tests) still gets a working HITL setup; explicit
        # config passed by the caller still wins.
        merged = {
            "memory_enabled": True,
            "hitl": {"enabled": True, "max_hitl": 8},
        }
        merged.update(config or {})
        super().__init__(config=merged)

    @property
    def name(self) -> str:
        return "svc-c2-019"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects InitializeNode + FinalizeNode
        self._nodes["pre_process"] = ChecklistGenerateNode()
        self._nodes["main"] = OnboardingWorkflowGraphNode(hitl=self.config.get("hitl"))
        self._nodes["post_process"] = CompletionReportNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


# agent.yaml module:"src.graph" class:"HROnboardingOrchestrationGraph" resolves this class directly.
Graph = HROnboardingOrchestrationGraph
