"""Seletores centralizados do portal Loterias Online CAIXA."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Selectors:
    privacy_yes_button: str = "//button[@id='adopt-accept-all-button']"
    terms_yes_button: str = "//a[@id='botaosim']"
    logged_off_login_button: str ="//div[@id='LoginHeaderView.html']//a[@id='btnLogin']"
    cpf_field: str = "//input[@id='username']"
    cpf_next_button: str = "//button[@id='button-submit']"
    receive_code_button: str = "//*[@id='form-login']//button[@name='login']"
    code_field: str = "//input[@id='codigo']"
    code_send_button: str = "//*[@id='form-login']//button[@name='login']"
    password_field: str = "//*[@id='password']"
    password_enter_button: str = "//*[@id='template-section']//button[text()='Entrar']"
    logged_in_login_button: str ="//div[@id='LoginHeaderView.html']//a[@id='suaconta']"
    logged_in_user_notifications_link: str ="//div[@id='LoginHeaderView.html']//a[@id='suaconta']"
    do_not_show_notification_checkbox: str ="//div[contains(@class,'modal-notificacao')]//input[@type='checkbox' and contains(@aria-label,'Não mostrar mais')]"
    close_notification_button: str ="//div[contains(@class,'modal-notificacao')]//button[contains(@class,'btn-fechar-notificacao')]"
    
    #notification_popup_close: str = "//*[@id='HeaderView.html']//button[text()='Fechar']"
    complete_game_button: str = "//*[@id='completeojogo']"
    add_to_cart_button: str = "//*[@id='colocarnocarrinho']"
    go_to_payment_button: str = "//*[@id='irparapagamento']"
    confirm_purchase_button: str = "//div[contains(@class,'modal-content')]//button[@id='confirma']"
    continue_payment_button: str = "//label[normalize-space()='Informe os dados do seu cartão de crédito:']/ancestor::div[contains(@class,'jumbotron')]//button[@id='pay']"
    security_code_field: str = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//input[@id='securityCode']"
    confirm_payment_button: str = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirmarModalConfirmacao']"
    finished_order_text: str = "//div[@id='containerProcessamento']//h3[contains(.,'Seu pedido foi realizado')]"
    logout_button: str = "//*[@id='sair']"

    close_bet_registration_alert_button: str = "//div[contains(@class,'modal-content')][.//p[contains(., 'O registro de apostas individuais para o concurso') and contains(., 'foi encerrado')]]//button[@id='fecharModalAlerta']"

    def modality_button(self, modality: str) -> str:
        return (
            f"//div[contains(@class,'new-card-modalidades')][.//h2[normalize-space()='{modality}']]"
            "//button[not(@tabindex='-1') and .//p[normalize-space()='Aposte']]"
        )

    def card_selector(self, last_digits: str) -> str:
        return f"//h4[.//img[@alt='Mercado Pago'] and contains(normalize-space(.),'{last_digits}')]"
