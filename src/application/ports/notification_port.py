"""Porta para notificações de falha operacional."""

from __future__ import annotations

from typing import Protocol

from application.dto import PurchaseResult
from domain import AutomationError, AutomationSession


class NotificationPort(Protocol):
    def start_whatsapp_session(self, session: AutomationSession) -> None:
        """Inicializa o WhatsApp Web quando disponível."""

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        """Encerra o WhatsApp Web quando disponível."""

    def notify_failure(self, whatsapp_enabled: bool, exc: AutomationError) -> bool:
        """Envia WhatsApp e usa e-mail como fallback."""

    def notify_success(self, session: AutomationSession, purchase: PurchaseResult) -> None:
        """Envia notificação de aposta finalizada."""
