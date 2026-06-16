"""Porta para notificações de falha operacional."""

from __future__ import annotations

from typing import Protocol

from domain import AutomationSession


class NotificationPort(Protocol):
    def start_whatsapp_session(self, session: AutomationSession) -> None:
        """Inicializa o WhatsApp Web quando disponível."""

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        """Encerra o WhatsApp Web quando disponível."""

    def notify_failure(self, session: AutomationSession, message: str) -> None:
        """Envia WhatsApp e usa e-mail como fallback."""
