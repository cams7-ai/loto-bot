"""Client HTTP para leitura do código de validação."""

from __future__ import annotations

import logging

import httpx

from application import ValidationCodePort
from domain import Operation, ExternalServiceError
from infrastructure import Settings
from shared import mask_sensitive_value


logger = logging.getLogger(__name__)


class GmailReaderClient(ValidationCodePort):
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.validation_code_wait_timeout_seconds + 5)

    def get_validation_code(self, operation: Operation) -> str:
        url = f"{self._settings.url_gmail_reader}/api/v1/validation-code"
        logger.info(
            "Chamando API Gmail Reader para buscar código de validação",
            extra=Operation.executed_operation(operation),
        )
        try:
            response = self._client.get(
                url,
                params={"waitTimeoutSeconds": self._settings.validation_code_wait_timeout_seconds},
                timeout=self._settings.validation_code_wait_timeout_seconds + 5,
            )
        except httpx.TimeoutException as exc:
            raise ExternalServiceError(
                "Tempo esgotado ao buscar o código de validação.",
                operation=operation,
            ) from exc
        if response.status_code >= 400:
            raise ExternalServiceError("Não foi possível buscar o código de validação.", operation=operation)

        payload = response.json()
        code = str(payload.get("code", "")).strip()
        if not code:
            raise ExternalServiceError("A API Gmail Reader não retornou código de validação.", operation=operation)
        mask_sensitive_value(code)
        return code
