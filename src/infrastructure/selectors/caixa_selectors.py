"""Seletores centralizados do portal Loterias Online CAIXA."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Selectors:
    privacy_yes_button: str = "//h3[normalize-space()='Aviso de privacidade']/ancestor::div[contains(@class,'adopt-c-bXGRNs')]//button[normalize-space()='Aceitar']"
    terms_yes_button: str = "//*[@id='botaosim']"
    home_access_button: str = "//*[@id='btnLogin']/span"
    cpf_field: str = "//*[@id='username']"
    cpf_next_button: str = "//*[@id='button-submit']"
    receive_code_button: str = "//*[@id='form-login']//button[text()='Receber código']"
    code_field: str = "//*[@id='codigo']"
    code_send_button: str = "//*[@id='form-login']//button[text()='Enviar']"
    password_field: str = "//*[@id='password']"
    password_enter_button: str = "//*[@id='template-section']//button[text()='Entrar']"
    notification_popup_close: str = "//*[@id='HeaderView.html']//button[text()='Fechar']"
    complete_game_button: str = "//*[@id='completeojogo']"
    add_to_cart_button: str = "//*[@id='colocarnocarrinho']"
    go_to_payment_button: str = "//*[@id='irparapagamento']"
    confirm_purchase_button: str = "//span[contains(.,'O Valor total da sua compra é de') and contains(.,'Confirma?')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirma']"
    continue_payment_button: str = "//label[normalize-space()='Informe os dados do seu cartão de crédito:']/ancestor::div[contains(@class,'jumbotron')]//button[@id='pay']"
    security_code_field: str = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//input[@id='securityCode']"
    confirm_payment_button: str = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirmarModalConfirmacao']"
    finished_order_text: str = "//div[@id='containerProcessamento']//h3[contains(.,'Seu pedido foi realizado')]"
    account_button: str = "//a[@id='suaconta']//span[normalize-space()='Minha Conta']"
    logout_button: str = "//*[@id='sair']"

    def modality_button(self, modality: str) -> str:
        return f"//h2[normalize-space()='{modality}']/ancestor::div[contains(@class,'new-card-modalidades')]//button[.//p[normalize-space()='Aposte']]"

    def card_selector(self, last_digits: str) -> str:
        return f"//h4[.//img[@alt='Mercado Pago'] and contains(normalize-space(.),'{last_digits}')]"
