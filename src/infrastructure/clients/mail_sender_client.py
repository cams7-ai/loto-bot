"""Client HTTP para envio de e-mail."""

from __future__ import annotations

import logging

import httpx

from domain import (
    FALLBACK_EMAIL_SEND_FAILED,
    ExternalServiceError,
    Operation,
)
from infrastructure.config import Settings

logger = logging.getLogger(__name__)


class MailSenderClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=10)

    def send(self, operation: Operation, subject: str, body: str) -> None:
        logger.info("Chamando API Mail Sender para enviar e-mail", extra=Operation.executed_operation(operation))
        response = self._client.post(
            f"{self._settings.mail_sender_url}/api/v1/mail/send",
            json={
                "to": self._settings.mail_to,
                "subject": subject,
                "body": body,
                "message_type": self._settings.mail_content_type,
            },
        )
        if response.status_code >= 400:
            raise ExternalServiceError(FALLBACK_EMAIL_SEND_FAILED, operation=operation)
