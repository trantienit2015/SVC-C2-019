# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `HROnboardingOrchestrationGraph` (`src/graph/graph.py`)
- **L1 Base**: AgentBaseGraph / AutonomousBaseGraph (circle one)
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

### Node Configuration

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | | | | InitializeNode (default) |
| pre_process | | | | |
| main | | | | |
| post_process | | | | |
| finalize | | | | FinalizeNode (default) |

### Data Flow

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry)
                                          pre_process
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| | | | |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [ ] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [ ] ConnectionPolicy (retry/timeout strategy)
- [ ] SecurityViolationError
- [ ] S-2: `_extra_security_gate_input()` — domain-specific input check hook
      (runs after the default PII scan; implement any domain checks needed — e.g. PII scan
      on additional fields, consent flag validation, input size limits, business rule gates;
      omit if the default framework scan on `user_input` / `validated_input` / `llm_response`
      is sufficient; **MUST NOT override `_security_gate_input()`** — `TypeError` at class definition)
- [ ] S-3: `_extra_security_gate_output()` — domain-specific output check hook
      (runs after the default credential scan; implement any domain checks needed — e.g.
      credential scan on nested fields, PII re-check on LLM output, content filtering,
      preservation verification; omit if the default scan on result string values is sufficient;
      **MUST NOT override `_security_gate_output()`** — `TypeError` at class definition)
- [ ] S-4: `emit_trace_event()` — at least one domain-specific event inside each `execute()`
      (**mandatory**; do NOT emit `node_start` / `node_complete` / `node_error` —
      `BaseNode.__call__()` emits these automatically; duplicates corrupt audit trail)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: Standalone / GraphNode (subgraph) / RemoteAgentNode (HTTP)
- **Composition target**: (if applicable)
- **Error propagation strategy**: propagate / handle

## Import Isolation Confirmation
- [ ] Template does not import agenticstar-platform SDK (Level 0)
- [ ] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | | |
| Composition pattern | | | | |
