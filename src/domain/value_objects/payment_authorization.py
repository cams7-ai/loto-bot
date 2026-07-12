"""Value object para autorização explícita de pagamento."""

from __future__ import annotations

from dataclasses import dataclass

from domain.exceptions import PaymentConfirmationDisabledError


@dataclass(frozen=True)
class PaymentAuthorization:
    confirmed: bool

    def require_confirmation(self) -> None:
        if not self.confirmed:
            raise PaymentConfirmationDisabledError()
