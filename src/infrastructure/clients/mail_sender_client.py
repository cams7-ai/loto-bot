"""Client HTTP para envio de e-mail."""

from __future__ import annotations

import httpx

from domain import ExternalServiceError
from infrastructure.config import Settings


class MailSenderClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=10)

    def send(self, subject: str, body: str) -> None:
        response = self._client.post(
            f"{self._settings.url_mail_sender}/api/v1/mail/send",
            json={
                "to": self._settings.mail_to,
                "subject": subject,
                "body": body,
                "message_type": self._settings.mail_type,
            },
        )
        if response.status_code >= 400:
            raise ExternalServiceError("Não foi possível enviar o e-mail de fallback.", operation="Envia e-mail")
