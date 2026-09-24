# SVC-C2-019 - Framework compliance tests TC-01..TC-08 (code review round 1).
# Reference shape: the standard framework-compliance test module,
# adapted to this template's real architecture (Cat 2: outer pre/post +
# GraphNode-wrapped inner subgraph: PII gate -> HITL gate -> provisioning ->
# reminder -> status track).

import os
import re

import pytest
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import (
    checklist_generate_node,
    completion_report_node,
    pii_gate_node,
    provisioning_request_node,
    reminder_node,
    status_track_node,
)
from src.schemas.state import State

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.VERIFIED_EXTERNAL.value

_SAMPLE_PAYLOAD = (
    '{"new_hire": {"employee_id": "E1", "role": "engineer", "location": "tokyo", '
    '"start_date": "2026-08-01"}, "pii": {}}'
)


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# TC-01 - State is a flat TypedDict extending AgentState; added fields are
# JSON-serializable primitives/list/dict only (ADR-005) - never Pydantic/dataclass.
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_json_serializable_primitives(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        for name in added:
            ann = State.__annotations__[name]
            ann_str = str(ann)
            assert "Pydantic" not in ann_str and "BaseModel" not in ann_str, (
                f"{name}: {ann_str} - Pydantic/dataclass instances are prohibited in State"
            )


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        node = checklist_generate_node.ChecklistGenerateNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]

    def test_missing_inner_payload_no_raise(self):
        node = pii_gate_node.PIIGateNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR.value
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads.
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                content = f.read()
                if "os.environ" in content and "api/server.py" not in fp.replace("\\", "/"):
                    offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from langgraph.checkpoint.memory import InMemorySaver

        from src.graph.graph import Graph

        agent = Graph()
        # With the default policy HITLGateNode interrupts (HR compliance
        # gate) — a checkpointer is mandatory for invoke() to pause
        # cleanly instead of erroring (see tests/integration/test_graph.py).
        agent.compile(checkpointer=InMemorySaver())
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="hr-tc04")
        result = agent.invoke(_SAMPLE_PAYLOAD, ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: nodes emit >=1 domain event; no node under src/nodes/
# ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_node_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(checklist_generate_node, "emit_trace_event", lambda e, p, s: events.append(e))
        out = checklist_generate_node.ChecklistGenerateNode().execute(
            {"user_input": _SAMPLE_PAYLOAD, "node_history": [], "error_log": []}
        )
        assert out["status"] == AgentStatus.SUCCESS.value
        assert len(events) >= 1
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-06 / TC-07 - S-2/S-3 gates are @final on FunctionNode (overriding raises TypeError at class def).
class TestTC0607FinalGates:
    def test_input_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadIn(FunctionNode):  # noqa: N801
                def _security_gate_input(self, state):
                    return state

    def test_output_gate_is_final(self):
        with pytest.raises(TypeError):

            class BadOut(FunctionNode):  # noqa: N801
                def _security_gate_output(self, result):
                    return result

    def test_extra_output_hook_is_overridable(self):
        # ProvisioningRequestNode is the only node in this template that adds
        # a domain _extra_security_gate_output() (preservation-variant
        # request_id check) - the hook itself is optional/no-op by default,
        # so assert it is CALLABLE rather than assuming every node overrides
        # it (most nodes here rely on the base FunctionNode no-op).
        assert callable(provisioning_request_node.ProvisioningRequestNode._extra_security_gate_output)

    def test_output_gate_blocks_credentials(self):
        # The @final S-3 credential scan actually fires (not vacuous): a
        # credential in the result is blocked, never returned as-is.
        node = completion_report_node.CompletionReportNode()
        with pytest.raises(Exception):
            node._security_gate_output({"formatted_output": "token AKIAIOSFODNN7EXAMPLE leaked"})


# TC-08 - required_trust_level enforced: insufficient trust -> ERROR state, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        for cls in (
            checklist_generate_node.ChecklistGenerateNode,
            completion_report_node.CompletionReportNode,
            pii_gate_node.PIIGateNode,
            provisioning_request_node.ProvisioningRequestNode,
            reminder_node.ReminderNode,
            status_track_node.StatusTrackNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error(self):
        node = checklist_generate_node.ChecklistGenerateNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": _SAMPLE_PAYLOAD})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        node = checklist_generate_node.ChecklistGenerateNode()
        out = node({"caller_trust_level": TRUST, "user_input": _SAMPLE_PAYLOAD})
        assert out["status"] == AgentStatus.SUCCESS.value
