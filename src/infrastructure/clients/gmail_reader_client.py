"""Client HTTP para leitura do código de validação."""

from __future__ import annotations

import httpx

from application.ports import ValidationCodePort
from domain import ExternalServiceError
from infrastructure.config import Settings
from shared import mask_sensitive_value


class GmailReaderClient(ValidationCodePort):
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.validation_code_wait_timeout_seconds + 5)

    def get_validation_code(self) -> str:
        url = f"{self._settings.url_gmail_reader}/api/v1/validation-code"
        response = self._client.get(
            url,
            params={"waitTimeoutSeconds": self._settings.validation_code_wait_timeout_seconds},
        )
        if response.status_code >= 400:
            raise ExternalServiceError("Não foi possível buscar o código de validação.", operation="Solicita o código de acesso")
        payload = response.json()
        code = str(payload.get("code", "")).strip()
        if not code:
            raise ExternalServiceError("A API Gmail Reader não retornou código de validação.", operation="Solicita o código de acesso")
        mask_sensitive_value(code)
        return code
