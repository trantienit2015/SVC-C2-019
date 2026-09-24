"""AgentCore Platform v1.0"""

# Domain service: role/location-specific onboarding checklist generation.
# Pure logic, no side effects, no credentials — nodes call this.

from __future__ import annotations

from typing import Any

# Base checklist tasks shared by every new hire, plus role/location-specific
# additions. Deliberately deterministic (no LLM call) — checklist content is
# a fixed HR/IT/Facilities catalog, not a generative task.
_BASE_TASKS = [
    {"task": "Issue employee ID badge", "department": "Facilities"},
    {"task": "Provision corporate email account", "department": "IT"},
    {"task": "Enroll in benefits orientation", "department": "HR"},
]

_ROLE_TASKS: dict[str, list[dict[str, str]]] = {
    "engineer": [
        {"task": "Provision developer laptop + VPN access", "department": "IT"},
        {"task": "Grant source-control + CI/CD access", "department": "IT"},
    ],
    "sales": [
        {"task": "Provision CRM account", "department": "IT"},
        {"task": "Assign sales territory", "department": "Sales Ops"},
    ],
    "manager": [
        {"task": "Grant approval workflow permissions", "department": "IT"},
        {"task": "Schedule leadership onboarding session", "department": "HR"},
    ],
}

_LOCATION_TASKS: dict[str, list[dict[str, str]]] = {
    "remote": [
        {"task": "Ship home-office equipment kit", "department": "Facilities"},
    ],
    "onsite": [
        {"task": "Assign desk + building access card", "department": "Facilities"},
    ],
}


def generate_checklist(role: str, location: str) -> list[dict[str, Any]]:
    """Build the role/location-specific onboarding checklist.

    Both ``role`` and ``location`` are matched case-insensitively against a
    known catalog; unknown values simply fall back to the base tasks only
    (fail-open on catalog gaps, not fail-closed — an unrecognized role must
    not block onboarding from starting).
    """
    tasks = list(_BASE_TASKS)
    tasks.extend(_ROLE_TASKS.get((role or "").strip().lower(), []))
    tasks.extend(_LOCATION_TASKS.get((location or "").strip().lower(), []))
    return [{**t, "status": "pending"} for t in tasks]
