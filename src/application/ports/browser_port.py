"""Porta de automação de navegador."""

from __future__ import annotations

from typing import Protocol

from domain import AutomationSession

class BrowserAutomationPort(Protocol):
    def start(self, session: AutomationSession) -> str:
        """Abre uma sessão persistente e retorna o tab_id."""

    def stop(self) -> None:
        """Fecha a sessão ativa."""

    def access_home(self, session: AutomationSession) -> None:
        """Acessa a home autenticável."""

    def access_lottery_portal(self, session: AutomationSession) -> None:
        """Acessa o portal Loterias Online."""

    def is_authenticated(self, click_login_button: bool) -> bool:
        """Verifica se a sessão está autenticada no portal."""

    def accept_terms(self, session: AutomationSession) -> None:
        """Aceita os termos de uso."""

    def submit_cpf(self, session: AutomationSession) -> None:
        """Informa o CPF."""

    def request_validation_code(self, session: AutomationSession) -> None:
        """Solicita o código de acesso."""

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        """Informa o código recebido."""

    def submit_password(self, session: AutomationSession) -> None:
        """Informa a senha."""

    def disable_notification(self) -> None:
        """Desabilita notificações do portal."""

    def select_lottery_modality(self, session: AutomationSession) -> None:
        """Seleciona a modalidade."""

    def choose_random_numbers(self, session: AutomationSession) -> None:
        """Completa o jogo com números aleatórios."""

    def add_bet_to_cart(self, session: AutomationSession) -> None:
        """Adiciona a aposta ao carrinho."""

    def confirm_purchase(self, session: AutomationSession) -> None:
        """Confirma a compra."""

    def select_payment_method(self, session: AutomationSession) -> None:
        """Seleciona a forma de pagamento."""

    def confirm_payment(self, session: AutomationSession) -> None:
        """Confirma o pagamento no portal."""

    def finish_bet(self, session: AutomationSession) -> str:
        """Finaliza a aposta e retorna o código de acompanhamento."""
