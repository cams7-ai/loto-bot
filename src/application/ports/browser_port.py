"""Porta de automação de navegador."""

from __future__ import annotations

from typing import Protocol

from application.dto import PurchaseResult
from domain import AutomationSession


class BrowserAutomationPort(Protocol):
    def start(self, session: AutomationSession) -> str:
        """Abre uma sessão persistente e retorna o tab_id."""

    def stop(self) -> None:
        """Fecha a sessão ativa."""

    def access_home(self) -> None:
        """Acessa a home autenticável."""

    def access_authenticated_home(self) -> None:
        """Acessa a home autenticada."""

    def is_already_authenticated(self) -> bool:
        """Apenas verifica se o usuário já está logado, sem clicar em nada."""

    def is_authenticated(self) -> bool:
        """Tenta acessar a área autenticada e verifica se o usuário está logado."""

    def accept_terms(self, session: AutomationSession) -> None:
        """Aceita os termos de uso."""

    def submit_cpf(self, session: AutomationSession) -> None:
        """Informa o CPF."""

    def is_valid_cpf(self) -> bool:
        """Verifica se o CPF informado é válido."""

    def validation_code_lookup_lead(self) -> int:
        """Tempo de antecedência para buscar o código de validação."""

    def request_validation_code(self, session: AutomationSession) -> None:
        """Solicita o código de acesso."""

    def submit_validation_code(self, session: AutomationSession, code: str) -> None:
        """Informa o código recebido."""

    def submit_password(self, session: AutomationSession) -> None:
        """Informa a senha."""

    def clear_shopping_cart(self, session: AutomationSession) -> None:
        """Limpa carrinho no portal."""

    def select_lottery_modality(self, session: AutomationSession) -> None:
        """Seleciona a modalidade."""

    def place_bet(self, session: AutomationSession) -> None:
        """Completa o jogo com números aleatórios."""
        """Adiciona a aposta ao carrinho."""

    def confirm_purchase(self, session: AutomationSession) -> None:
        """Confirma a compra."""

    def confirm_payment(self) -> None:
        """Seleciona a forma de pagamento."""
        """Confirma o pagamento no portal."""

    def check_bet_processing(self, session: AutomationSession) -> None:
        """Acessa a página de conferência de processamento da aposta."""

    def check_your_purchases(self, session: AutomationSession) -> None:
        """Acessa a página de conferência de compras."""

    def finish_bet(self, session: AutomationSession) -> PurchaseResult:
        """Finaliza a aposta e retorna os dados da compra."""
