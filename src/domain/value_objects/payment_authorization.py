"""Value object para autorização explícita de pagamento."""

from __future__ import annotations

from dataclasses import dataclass

from domain.enums import Operation
from domain.exceptions import PaymentConfirmationDisabledError

@dataclass(frozen=True)
class PaymentAuthorization:
    confirmed: bool

    def require_confirmation(self) -> None:
        if not self.confirmed:
            raise PaymentConfirmationDisabledError(
                "A confirmação de pagamento real está desabilitada. Configure CONFIRM_PAYMENT=true apenas quando desejar executar o pagamento.",
                operation=Operation.CONFIRM_PAYMENT,
            )
