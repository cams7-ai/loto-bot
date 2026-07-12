"""Porta para notificações de falha operacional."""

from __future__ import annotations

from typing import Protocol

from domain import AutomationSession, AutomationError

class NotificationPort(Protocol):
    def start_whatsapp_session(self, session: AutomationSession) -> None:
        """Inicializa o WhatsApp Web quando disponível."""

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        """Encerra o WhatsApp Web quando disponível."""

    def notify_failure(self, whatsapp_enabled: bool, exc: AutomationError) -> bool:
        """Envia WhatsApp e usa e-mail como fallback."""
