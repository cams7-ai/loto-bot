"""Porta para notificações de falha operacional."""

from __future__ import annotations

from typing import Protocol

from domain import ErrorCode, AutomationSession

class NotificationPort(Protocol):
    def start_whatsapp_session(self, session: AutomationSession) -> None:
        """Inicializa o WhatsApp Web quando disponível."""

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        """Encerra o WhatsApp Web quando disponível."""

    def notify_failure(self, session: AutomationSession, error_code: ErrorCode, whatsapp_message: str, mail_message: str) -> bool:
        """Envia WhatsApp e usa e-mail como fallback."""
