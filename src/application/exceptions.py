from __future__ import annotations


class PortalBetFiltersValidationError(ValueError):
    def __init__(self, messages: list[str]) -> None:
        self.messages = list(messages)
        super().__init__("; ".join(self.messages))
