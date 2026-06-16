"""Utilitários para mascarar dados sensíveis."""

from __future__ import annotations


def mask_sensitive_value(value: str | None, *, visible: int = 2) -> str:
    if value is None:
        return ""
    normalized = str(value)
    if len(normalized) <= visible:
        return "*" * len(normalized)
    return f"{'*' * (len(normalized) - visible)}{normalized[-visible:]}"
