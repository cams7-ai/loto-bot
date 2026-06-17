"""Porta de automação de navegador."""

from __future__ import annotations

from typing import Protocol

from domain import AutomationSession


class BrowserAutomationPort(Protocol):
    def start(self, session: AutomationSession) -> str:
        """Abre uma sessão persistente e retorna o tab_id."""

    def stop(self) -> None:
        """Fecha a sessão ativa."""

    def access_lottery_portal(self, session: AutomationSession) -> None:
        """Acessa o portal Loterias Online CAIXA."""

    def accept_terms(self, session: AutomationSession) -> None:
        """Aceita os termos de uso."""

    def access_home(self, session: AutomationSession) -> None:
        """Acessa a home autenticável."""

    def submit_cpf(self, session: AutomationSession) -> None:
        """Informa o CPF."""

    def request_validation_code(self, session: AutomationSession) -> None:
        """Solicita o código de acesso."""

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        """Informa o código recebido."""

    def submit_password(self, session: AutomationSession) -> None:
        """Informa a senha."""

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

    def is_authenticated(self, session: AutomationSession) -> bool:
        """Verifica se a sessão está autenticada no portal."""
