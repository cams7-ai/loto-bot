"""Client HTTP local ou AWS Lambda para envio de e-mail."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from botocore.config import Config

from domain import (
    ErrorMessage,
    ExternalServiceError,
    Operation,
)
from infrastructure.config import Settings

logger = logging.getLogger(__name__)


class MailSenderClient:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    def _lambda_client(self) -> Any:
        if self._client is None:
            self._client = __import__("boto3").client("lambda", config=Config(use_dualstack_endpoint=True))
        return self._client

    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10)
        return self._client

    def send(self, operation: Operation, subject: str, body: str) -> None:
        logger.info("Chamando API Mail Sender para enviar e-mail", extra=Operation.executed_operation(operation))
        request_payload = {
            "to": self._settings.mail_to,
            "subject": subject,
            "body": body,
            "message_type": self._settings.mail_content_type,
        }
        if self._settings.integration_mode == "LOCAL":
            response = self._http_client().post(
                f"{self._settings.mail_sender_url}/api/v1/mail/send",
                json=request_payload,
            )
            failed = response.status_code >= 400
        else:
            response = self._lambda_client().invoke(
                FunctionName=self._settings.mail_sender_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(request_payload).encode("utf-8"),
            )
            payload = json.loads(response["Payload"].read())
            failed = bool(response.get("FunctionError")) or payload.get("statusCode", 500) >= 400

        if failed:
            raise ExternalServiceError(ErrorMessage.FALLBACK_EMAIL_SEND_FAILED, operation=operation)
