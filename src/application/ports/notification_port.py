"""Porta para notificações de falha operacional."""

from __future__ import annotations

from typing import Protocol

from application.dto import PortalBetResult, PurchaseResult
from domain import AutomationError, AutomationSession, NotificationChannel


class NotificationPort(Protocol):
    def start_whatsapp_session(self, session: AutomationSession) -> None:
        """Inicializa o WhatsApp Web quando disponível."""

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        """Encerra o WhatsApp Web quando disponível."""

    def notify_failure(self, whatsapp_enabled: bool, exc: AutomationError) -> bool:
        """Envia WhatsApp e usa e-mail como fallback."""

    def notify_success(self, session: AutomationSession, purchase: PurchaseResult) -> None:
        """Envia notificação de aposta finalizada."""

    def notify_draw_results(
        self,
        session: AutomationSession,
        bets: list[PortalBetResult],
    ) -> NotificationChannel:
        """Notifica uma conferência consolidada usando e-mail apenas como fallback."""
