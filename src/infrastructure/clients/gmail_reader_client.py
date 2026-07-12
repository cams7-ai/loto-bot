"""Client HTTP para leitura do código de validação."""

from __future__ import annotations

import logging

import httpx

from application import ValidationCodePort
from domain import (
    GMAIL_READER_API_VALIDATION_CODE_NOT_RETURNED,
    VALIDATION_CODE_FETCH_FAILED,
    VALIDATION_CODE_FETCH_TIMEOUT,
    ExternalServiceError,
    Operation,
)
from infrastructure.config import Settings
from shared import mask_sensitive_value

logger = logging.getLogger(__name__)


class GmailReaderClient(ValidationCodePort):
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.validation_code_wait_timeout_seconds + 5)

    def get_validation_code(self, operation: Operation) -> str:
        url = f"{self._settings.gmail_reader_url}/api/v1/validation-code"
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
            raise ExternalServiceError(VALIDATION_CODE_FETCH_TIMEOUT, operation=operation) from exc

        if response.status_code >= 400:
            raise ExternalServiceError(VALIDATION_CODE_FETCH_FAILED, operation=operation)

        payload = response.json()
        code = str(payload.get("code", "")).strip()
        if not code:
            raise ExternalServiceError(GMAIL_READER_API_VALIDATION_CODE_NOT_RETURNED, operation=operation)

        mask_sensitive_value(code)
        return code
