"""AgentCore Platform v1.0"""

# Domain service: My Number (特定個人情報, 番号法) + personal-data masking.
# Pure logic, no side effects, no credentials — PIIGateNode calls this.
#
# This is the core 番号法 (My Number Act) implementation: My Number and 5 other
# PII field types are masked BEFORE any downstream node (ProvisioningRequestNode,
# ReminderNode, StatusTrackNode, CompletionReportNode) — the raw values are
# never returned, only field NAMES that were present + masked, so callers can
# audit what was redacted without the redacted content itself ever touching
# AgentState (PIIGateNode is an independent S-2 node).

from __future__ import annotations

from typing import Any

# The 6 PII field types this gate is responsible for: My Number + 5 others.
PII_FIELDS = (
    "my_number",  # 特定個人情報 (Individual Number) — 番号法-regulated
    "full_name",
    "home_address",
    "phone_number",
    "personal_email",
    "bank_account",
)


def mask_pii(raw_pii: dict[str, Any] | None) -> tuple[list[str], bool]:
    """Detect + mask the 6 regulated PII field types.

    Returns ``(masked_field_names, my_number_detected)``. The raw values
    themselves are discarded here and MUST NOT be propagated by the caller —
    this function's return value carries no PII content, only field-name
    metadata for audit purposes.
    """
    if not isinstance(raw_pii, dict):
        return [], False

    masked = [field for field in PII_FIELDS if raw_pii.get(field)]
    my_number_detected = bool(raw_pii.get("my_number"))
    return masked, my_number_detected
