"""Seletores centralizados do portal Loterias Online CAIXA."""

from __future__ import annotations

from enum import StrEnum


class Selectors(StrEnum):
    # Aceita os termos de uso
    PRIVACY_YES_BUTTON = "//button[@id='adopt-accept-all-button']"
    TERMS_YES_BUTTON = "//a[@id='botaosim']"
    # Home do usuário deslogado
    LOGGED_OFF_LOGIN_BUTTON = "//div[@id='LoginHeaderView.html']//a[@id='btnLogin']"
    # Informa o CPF
    CPF_FIELD = "//input[@id='username']"
    CPF_NEXT_BUTTON = "//button[@id='button-submit']"
    CPF_INVALID_ALERT = "//div[@id='username-alert' and @style='display: block;']"
    # Solicita o código de acesso
    RECEIVE_CODE_BUTTON = "//*[@id='form-login']//button[@name='login']"
    # Informa o código de acesso
    CODE_FIELD = "//input[@id='codigo']"
    CODE_SEND_BUTTON = "//*[@id='form-login']//button[@name='login']"
    # Informa a senha
    PASSWORD_FIELD = "//*[@id='password']"
    PASSWORD_ENTER_BUTTON = "//*[@id='template-section']//button[text()='Entrar']"
    PASSWORD_INVALID_ALERT = "//section[@id='template-section']//div[contains(@class,'alert-error') and normalize-space()='Senha inválida.']"    
    # Home quando o usuário está logado
    LOGGED_IN_LOGIN_BUTTON = "//div[@id='LoginHeaderView.html']//a[@id='suaconta']"
    DO_NOT_SHOW_NOTIFICATION_CHECKBOX = "//div[contains(@class,'modal-notificacao')]//input[@type='checkbox' and contains(@aria-label,'Não mostrar mais')]"
    CLOSE_NOTIFICATION_BUTTON = "//div[contains(@class,'modal-notificacao')]//button[contains(@class,'btn-fechar-notificacao')]"
    # Carrinho de compras
    SHOPPING_CART_COUNT = "normalize-space(//div[@id='LoginHeaderView.html']//a[@id='carrinho'])"
    SHOPPING_CART_BUTTON = "//div[@id='LoginHeaderView.html']//a[@id='carrinho']"
    CLEAR_CART_BUTTON = "//button[@id='limparcarrinho']"
    CONFIRM_CLEAR_CART_BUTTON = (
        "//div[@id='modalUl']"
        "[.//span[normalize-space(.)='Deseja realmente remover todas as apostas do carrinho?']]"
        "//button[contains(@class,'data-limpar-carrinho')]"
    )
    # Seleciona uma modalidade
    COMPLETE_GAME_BUTTON = "//*[@id='completeojogo']"
    # Carrinho de compras
    ADD_TO_CART_BUTTON = "//*[@id='colocarnocarrinho']"
    GO_TO_PAYMENT_BUTTON = "//*[@id='irparapagamento']"
    CONFIRM_PURCHASE_BUTTON = "//div[contains(@class,'modal-content')]//button[@id='confirma']"
    CONTINUE_PAYMENT_BUTTON = "//label[normalize-space()='Informe os dados do seu cartão de crédito:']/ancestor::div[contains(@class,'jumbotron')]//button[@id='pay']"
    SECURITY_CODE_FIELD = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//input[@id='securityCode']"
    CONFIRM_PAYMENT_BUTTON = "//p[contains(normalize-space(.),'Digite o código de Segurança do seu cartão')]/ancestor::div[contains(@class,'modal-content')]//button[@id='confirmarModalConfirmacao']"
    FINISHED_ORDER_TEXT = "//div[@id='containerProcessamento']//h3[contains(.,'Seu pedido foi realizado')]"
    LOGOUT_BUTTON = "//*[@id='sair']"
    CLOSE_BET_REGISTRATION_ALERT_BUTTON = "//div[contains(@class,'modal-content')][.//p[contains(., 'O registro de apostas individuais para o concurso') and contains(., 'foi encerrado')]]//button[@id='fecharModalAlerta']"

    @staticmethod
    def modality_button(modality: str) -> str:
        return (
            f"//div[contains(@class,'new-card-modalidades')][.//h2[normalize-space()='{modality}']]"
            "//button[not(@tabindex='-1') and .//p[normalize-space()='Aposte']]"
        )

    @staticmethod
    def card_selector(last_digits: str) -> str:
        return f"//h4[.//img[@alt='Mercado Pago'] and contains(normalize-space(.),'{last_digits}')]"
