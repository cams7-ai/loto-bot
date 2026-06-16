"""Client HTTP para WhatsApp Notify."""

from __future__ import annotations

import logging

import httpx

from domain import ExternalServiceError
from infrastructure.config import Settings


logger = logging.getLogger(__name__)


class WhatsAppNotifyClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.Client(timeout=settings.whatsapp_timeout_seconds + 5)

    def start_session(self) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para iniciar sessão",
            extra={"executed_operation": "Inicia sessão do WhatsApp Web"},
        )
        response = self._client.get(
            f"{self._settings.url_whatsapp_notify}/whatsapp/session/start",
            params={
                "headless": self._settings.whatsapp_headless,
                "timeoutInSeconds": self._settings.whatsapp_timeout_seconds,
            },
        )
        if response.status_code >= 400:
            self._raise_from_error(response, "Inicia sessão do WhatsApp Web")
        return str(response.json().get("status", ""))

    def stop_session(self) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para encerrar sessão",
            extra={"executed_operation": "Encerra sessão do WhatsApp Web"},
        )
        response = self._client.get(f"{self._settings.url_whatsapp_notify}/whatsapp/session/stop")
        if response.status_code >= 400:
            self._raise_from_error(response, "Encerra sessão do WhatsApp Web")
        return str(response.json().get("status", ""))

    def status(self) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para consultar sessão",
            extra={"executed_operation": "Consulta sessão do WhatsApp Web"},
        )
        response = self._client.get(f"{self._settings.url_whatsapp_notify}/whatsapp/session/status")
        if response.status_code >= 400:
            self._raise_from_error(response, "Consulta sessão do WhatsApp Web")
        return str(response.json().get("status", ""))

    def send_message(self, message: str) -> str:
        logger.info(
            "Chamando API WhatsApp Notify para enviar mensagem",
            extra={"executed_operation": "Envia notificação pelo WhatsApp Web"},
        )
        response = self._client.post(
            f"{self._settings.url_whatsapp_notify}/whatsapp/messages/send",
            json={"contact": self._settings.whatsapp_contact, "message": message},
        )
        if response.status_code >= 400:
            self._raise_from_error(response, "Envia notificação pelo WhatsApp Web")
        return str(response.json().get("status", ""))

    @staticmethod
    def _raise_from_error(response: httpx.Response, operation: str) -> None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") or "Serviço WhatsApp Notify indisponível."
        raise ExternalServiceError(str(message), operation=operation)
