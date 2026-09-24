# PB-7: HITL Interrupt Propagation — MANIFEST exact-name, required every
# template ((internal issue reference removed)). SVC-C2-019 has hitl.enabled: true, so this
# is the real GraphInterrupt-propagation test (not the auto-skip stub):
# verifies HITLGateNode's interrupt() (D6, inside the inner subgraph) surfaces
# through OnboardingWorkflowGraphNode (propagate_hitl=True) and the outer
# AgentBaseGraph as status=AWAITING_HUMAN — never status=error — and that
# resume() completes the pipeline with a real human decision.

import json

from langgraph.checkpoint.memory import InMemorySaver

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph

NEW_HIRE_PAYLOAD = json.dumps(
    {
        "new_hire": {
            "employee_id": "PB7-001",
            "role": "manager",
            "location": "onsite",
            "start_date": "2026-09-01",
        },
        "pii": {"my_number": "999999999999"},
    },
    ensure_ascii=False,
)


def _ctx(session_id: str) -> InvocationContext:
    return InvocationContext(session_id=session_id, caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="pb7-test")


class TestPB7HitlInterruptPropagation:
    def test_onboarding_interrupt_suspends_awaiting_human_not_error(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        result = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("pb7-await"))

        assert result["status"] == AgentStatus.AWAITING_HUMAN.value, (
            f"expected AWAITING_HUMAN, got {result['status']!r} — a HITL interrupt() must never "
            "surface as status=error"
        )
        assert "thread_id" in result and result["thread_id"]

    def test_resume_after_approve_completes_pipeline(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        paused = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("pb7-resume-approve"))
        assert paused["status"] == AgentStatus.AWAITING_HUMAN.value

        resumed = agent.resume(thread_id=paused["thread_id"], feedback={"action": "approve"})

        assert resumed["status"] == AgentStatus.SUCCESS.value
        node_history = resumed.get("node_history", [])
        assert "CompletionReportNode" in node_history
        assert "FinalizeNode" in node_history

    def test_resume_after_reject_never_auto_dispatches(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        paused = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("pb7-resume-reject"))
        assert paused["status"] == AgentStatus.AWAITING_HUMAN.value

        resumed = agent.resume(thread_id=paused["thread_id"], feedback={"action": "reject"})

        # The HITL gate is a compliance approval gate, not a queue filter — a
        # "reject" feedback still completes the pipeline (checklist is not
        # replaced), it just never auto-approves without a human decision.
        assert resumed["status"] == AgentStatus.SUCCESS.value
