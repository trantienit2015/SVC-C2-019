# SVC-C2-019 — HR Onboarding Process Orchestration Agent

> **Category**: Cat 2 (orchestrates multiple steps to accomplish a specific use case)
> **Industry**: SVC

## Overview

Orchestrates the operational side of employee onboarding. Given a new-hire
record, the agent builds the onboarding checklist, screens the payload for
personal data, suspends for a human compliance approval, then dispatches the
provisioning requests (accounts, access, equipment), issues reminders for
outstanding items, tracks completion status and renders a completion report.

The pipeline runs as a Cat 2 composition: an outer graph builds the checklist
and renders the report, while the domain workflow (personal-data gate →
approval gate → provisioning → reminders → status tracking) runs as an inner
subgraph.

Provisioning requests carry real access consequences, so the approval gate
never approves on its own. When a human can answer, the run suspends for an
HR decision before any request is dispatched, and that interrupt is surfaced
from the inner workflow to the caller. When no human can answer (an automated
caller, or a deployment with `hitl.confirmation_required: false` in
`config/config.yaml`, which is how this template ships), the run completes but
every checklist item is marked `hr_approval: pending` and the matching
provisioning requests are recorded as `pending_hr_approval` rather than
`requested`. Set `hitl.confirmation_required: true` once your deployment has a
way to resume a suspended run.

The agent is fully deterministic — it calls no language model and needs no
model API credentials.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
