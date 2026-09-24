# SVC-C2-019 — Integration Test: full outer graph (compile + invoke + resume)
#
# With the default policy (hitl.confirmation_required absent/true) HITLGateNode
# (inner subgraph) calls interrupt() and OnboardingWorkflowGraphNode.propagate_hitl
# surfaces it to the outer graph — a valid new-hire record suspends the whole
# agent as AWAITING_HUMAN before provisioning requests are dispatched.
# TestDeploymentHitlPolicy covers the shipped config/config.yaml policy.

import json

from langgraph.checkpoint.memory import InMemorySaver

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph

NEW_HIRE_PAYLOAD = json.dumps(
    {
        "new_hire": {
            "employee_id": "E-100",
            "role": "engineer",
            "location": "remote",
            "start_date": "2026-08-01",
        },
        "pii": {
            "my_number": "123456789012",
            "full_name": "Taro Yamada",
            "home_address": "1-1-1 Chiyoda, Tokyo",
        },
    },
    ensure_ascii=False,
)


def _ctx(session_id: str) -> InvocationContext:
    return InvocationContext(
        session_id=session_id,
        caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
        caller_id="integration-test",
    )


class TestGraphIntegration:
    def test_new_hire_onboarding_suspends_awaiting_human_not_error(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        result = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("it-await"))

        assert result["status"] == AgentStatus.AWAITING_HUMAN.value, (
            f"expected AWAITING_HUMAN, got {result['status']!r} — HR compliance "
            "interrupt() must never surface as status=error"
        )
        assert result["thread_id"]

    def test_resume_after_hr_approval_completes_pipeline(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        paused = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("it-resume-approve"))
        assert paused["status"] == AgentStatus.AWAITING_HUMAN.value

        resumed = agent.resume(thread_id=paused["thread_id"], feedback={"action": "approve"})

        assert resumed["status"] == AgentStatus.SUCCESS.value
        node_history = resumed.get("node_history", [])
        assert "CompletionReportNode" in node_history
        assert "FinalizeNode" in node_history

        report = resumed.get("output") or {}
        assert report.get("employee_id") == "E-100"
        assert report.get("checklist_task_count", 0) > 0
        assert report.get("provisioning_request_count", 0) > 0
        assert report.get("pii_masked_field_count", 0) == 3

    def test_missing_required_field_rejects_before_hitl(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        bad_payload = json.dumps({"new_hire": {"employee_id": "E-999"}, "pii": {}})
        result = agent.invoke(bad_payload, ctx=_ctx("it-reject"))

        # ChecklistGenerateNode rejects before the inner HITL subgraph ever runs.
        assert result["status"] in (AgentStatus.ERROR.value, AgentStatus.CANCELLED.value)

    def test_malformed_input_does_not_raise(self):
        agent = Graph()
        agent.compile(checkpointer=InMemorySaver())

        result = agent.invoke("not valid json", ctx=_ctx("it-malformed"))

        assert result["status"] in (AgentStatus.ERROR.value, AgentStatus.CANCELLED.value)


def _deployed_config(confirmation_required: bool) -> dict:
    import pathlib

    import yaml

    cfg = yaml.safe_load((pathlib.Path(__file__).resolve().parents[2] / "config" / "config.yaml").read_text(encoding="utf-8"))
    cfg["hitl"]["confirmation_required"] = confirmation_required
    return cfg


class TestDeploymentHitlPolicy:
    def test_shipped_config_defers_hr_approval_and_completes(self):
        cfg = _deployed_config(confirmation_required=False)
        assert cfg["hitl"]["enabled"] is True and cfg["memory_enabled"] is True
        agent = Graph(config=cfg)
        agent.compile(checkpointer=InMemorySaver())

        result = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("it-policy-defer"))

        assert result["status"] == AgentStatus.SUCCESS.value
        assert "CompletionReportNode" in result.get("node_history", [])
        inner = agent._nodes["main"].get_subgraph()._nodes["hitl_gate"]
        assert inner._confirmation_required is False

    def test_confirmation_required_true_restores_the_gate(self):
        agent = Graph(config=_deployed_config(confirmation_required=True))
        agent.compile(checkpointer=InMemorySaver())

        result = agent.invoke(NEW_HIRE_PAYLOAD, ctx=_ctx("it-policy-gate"))

        assert result["status"] == AgentStatus.AWAITING_HUMAN.value
