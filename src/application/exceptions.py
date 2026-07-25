from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationErrorDetail:
    field: str
    rejected_value: str
    message: str
    allowed_values: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "field": self.field,
            "rejected_value": self.rejected_value,
        }
        if self.allowed_values is not None:
            detail["allowed_values"] = self.allowed_values
        detail["message"] = self.message
        return detail


class PortalBetFiltersValidationError(ValueError):
    def __init__(self, details: list[ValidationErrorDetail]) -> None:
        self.details = list(details)
        super().__init__("; ".join(detail.message for detail in self.details))
