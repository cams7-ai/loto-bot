"""Client HTTP para WhatsApp Notify."""

from __future__ import annotations

import logging

import httpx

from domain import ExternalServiceError, Operation
from infrastructure.config import Settings

logger = logging.getLogger(__name__)


class WhatsAppNotifyClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.whatsapp_timeout_seconds + 5)

    def start_session(self, operation: Operation) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para iniciar sessão",
            extra=Operation.executed_operation(operation),
        )
        response = self._client.get(
            f"{self._settings.whatsapp_notify_url}/whatsapp/session/start",
            params={
                "headless": self._settings.whatsapp_headless,
                "timeoutInSeconds": self._settings.whatsapp_timeout_seconds,
            },
        )
        if response.status_code >= 400:
            self._raise_from_error(response, operation)
        return str(response.json().get("status", ""))

    def stop_session(self, operation: Operation) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para encerrar sessão",
            extra=Operation.executed_operation(operation),
        )
        response = self._client.get(f"{self._settings.whatsapp_notify_url}/whatsapp/session/stop")
        if response.status_code >= 400:
            self._raise_from_error(response, operation)
        return str(response.json().get("status", ""))

    def status(self, operation: Operation) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para consultar sessão",
            extra=Operation.executed_operation(operation),
        )
        response = self._client.get(f"{self._settings.whatsapp_notify_url}/whatsapp/session/status")
        if response.status_code >= 400:
            self._raise_from_error(response, operation)
        return str(response.json().get("status", ""))

    def send_message(self, operation: Operation, message: str) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para enviar mensagem",
            extra=Operation.executed_operation(operation),
        )
        response = self._client.post(
            f"{self._settings.whatsapp_notify_url}/whatsapp/messages/send",
            json={"contact": self._settings.whatsapp_contact, "message": message},
        )
        if response.status_code >= 400:
            self._raise_from_error(response, operation)
        return str(response.json().get("status", ""))

    @staticmethod
    def _raise_from_error(response: httpx.Response, operation: Operation) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") or "Serviço WhatsApp Notify indisponível."
        raise ExternalServiceError(str(message), operation=operation)
