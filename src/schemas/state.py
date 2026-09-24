"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict. LangGraph checkpoints use msgpack
# serialization, so only plain serializable fields are allowed. Do NOT add
# credentials or secrets. All agent-specific fields are NotRequired (project standard) —
# they may be absent from an early checkpoint or before the node that fills
# them has run.
#
# Raw PII (My Number + 5 other field types) is NEVER stored here — PIIGateNode
# (inner subgraph, first node) masks it in-flight and only field NAMES that
# were masked are recorded (pii_masked_fields), never the raw values.

from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """State for the HR Onboarding Process Orchestration Agent (SVC-C2-019).

    Inner-subgraph fields travel as a JSON string via ``validated_input``
    (Cat 2 GraphNode boundary — the inner graph never sees the outer state
    directly) and are re-materialized here by ``merge_output()`` once the
    inner subgraph completes.
    """

    # -- outer pre_process (ChecklistGenerateNode) --
    new_hire_record: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
    onboarding_checklist: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    rejected_records: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]

    # -- merged back from the inner subgraph (OnboardingWorkflowGraphNode.merge_output) --
    pii_masked_fields: NotRequired[list[str]]  # type: ignore[valid-type]
    my_number_detected: NotRequired[bool]  # type: ignore[valid-type]
    provisioning_requests: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    reminders_sent: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]
    department_status: NotRequired[list[dict[str, Any]]]  # type: ignore[valid-type]

    # -- outer post_process (CompletionReportNode) --
    completion_report: NotRequired[dict[str, Any]]  # type: ignore[valid-type]
