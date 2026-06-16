"""Exceções de domínio da automação."""

from __future__ import annotations


class AutomationError(RuntimeError):
    code = "FALHA_NA_AUTOMACAO"

    def __init__(self, message: str, *, operation: str | None = None) -> None:
        self.operation = operation
        super().__init__(message)


class BrowserSessionOpenError(AutomationError):
    code = "SESSAO_JA_ABERTA"


class BrowserSessionClosedError(AutomationError):
    code = "SESSAO_FECHADA"


class PaymentConfirmationDisabledError(AutomationError):
    code = "CONFIRMACAO_PAGAMENTO_DESABILITADA"


class ExternalServiceError(AutomationError):
    code = "SERVICO_EXTERNO_INDISPONIVEL"
