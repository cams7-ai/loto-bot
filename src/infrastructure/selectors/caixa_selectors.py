"""Seletores centralizados do portal Loterias Online CAIXA."""

from __future__ import annotations

from enum import StrEnum
from domain import LotteryModality
from infrastructure.selectors.lottery_modality_builder import LotteryModalityBuilder


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
    # Fechar modal de alerta de encerramento de registro de apostas individuais para o concurso
    DO_NOT_SHOW_NOTIFICATION_CHECKBOX = "//div[contains(@class,'modal-notificacao')]//input[@type='checkbox' and contains(@aria-label,'mostrar mais')]"
    CLOSE_NOTIFICATION_BUTTON = "//div[contains(@class,'modal-notificacao')]//button[contains(@class,'btn-fechar-notificacao')]"
    # Aceitar termos de uso
    TERMS_OF_USE_CHECKBOX = "//input[@type='checkbox' and @id='termodeuso']"
#    NEWS_CHECKBOX = "//input[@type='checkbox' and @id='noticias']"
    ACCEPT_TERMS_OF_USE_BUTTON = "//button[contains(@class,'data-finalizarcadastro') and normalize-space()='Aceitar Termos de Uso']"
    # Limpar carrinho de compras
    SHOPPING_CART_BUTTON = "//div[@id='LoginHeaderView.html']//a[@id='carrinho']"
    CLEAR_CART_BUTTON = "//button[@id='limparcarrinho']"
    CONFIRM_CLEAR_CART_BUTTON = (
        "//div[@id='modalUl']"
        "[.//span[normalize-space(.)='Deseja realmente remover todas as apostas do carrinho?']]"
        "//button[contains(@class,'data-limpar-carrinho')]"
    )
    # Seleciona uma modalidade
    CLOSE_BET_REGISTRATION_ALERT_BUTTON = "//div[contains(@class,'modal-content')][.//p[contains(., 'O registro de apostas individuais para o concurso') and contains(., 'foi encerrado')]]//button[@id='fecharModalAlerta']"
    # Realiza aposta
    COMPLETE_GAME_BUTTON = "//button[@id='completeojogo']"
    ADD_TO_CART_BUTTON = "//button[@id='colocarnocarrinho']"
    GO_TO_PAYMENT_BUTTON = "//button[@id='irparapagamento']"    
    # Confirmar pagamento
    CONFIRM_MODAL_NO_REVIEW_CART_BUTTON = "//div[@id='simnao-cancel']//button[contains(@class,'data-cancelar-modal-confirmacao')]"
    CONFIRM_PURCHASE_BUTTON = "//div[@id='ModalConfirmacaoValor']//button[@id='confirma']"
    DAILY_PURCHASE_LIMIT_ALERT_CLOSE_BUTTON = "//button[contains(@class,'close')]/ancestor::div[@id='mensagem_alert']//div[@id='div_alertas'][contains(normalize-space(.), 'limite máximo diário para compras')]"
    CONTINUE_PAYMENT_BUTTON = "//div[@id='divMeioPagamento']//button[@id='pay']"
    SECURITY_CODE_FIELD = "//div[@id='confirm-cancel-cvv']//input[@id='securityCode']"
    CONFIRM_PAYMENT_BUTTON = "//div[@id='confirm-cancel-cvv']//button[@id='confirmarModalConfirmacao']"
    # Confira a suas compras
    TRACK_YOUR_PURCHASES_BUTTON = "//div[@id='containerProcessamento']//button[@id='pay']"
    # Finalizar aposta
    BET_TABLE_ROWS = "//table[contains(@class,'tab-apostas')]//tbody/tr"

#    FINISHED_ORDER_TEXT = "//div[@id='containerProcessamento']//h3[contains(.,'Seu pedido foi realizado')]"
#    LOGOUT_BUTTON = "//*[@id='sair']"    
#    BET_CANNOT_BE_PROCESSED_ALERT = "//div[@id='div_alertas' and contains(normalize-space(.), 'não poderão ser efetivadas')]" # A(s) aposta(s) apresentada(s) a seguir não poderão ser efetivadas, pois o concurso/modalidade não está(ão) disponível(s) para captação: Mega-Sena
#    OVERNIGHT_BET_PROCESSING_ALERT = "//div[@id='div_alertas' and contains(normalize-space(.), 'apostas realizadas entre 22:00:00 e 05:00:00')]" # As apostas realizadas entre 22:00:00 e 05:00:00 permanecerão na situação "Pagamento recebido - Aguardando efetivação da aposta" até sua atualização de status, que ocorrerá a partir das 05:00:00

    # Seleciona uma modalidade
    @staticmethod
    def modality_button(lottery_modality: str) -> str | None:
        modality = LotteryModalityBuilder.get_lottery_modality(LotteryModality.from_string(lottery_modality))
        if modality is None:
            return None

        return (
            f"//div[contains(@class,'new-card-modalidades')][.//h2[normalize-space()='{modality}']]"
            "//button[.//p[normalize-space()='Aposte']]"
        )

    # Seleciona uma modalidade
    @staticmethod
    def disabled_modality_button(lottery_modality: str) -> str | None:
        modality = LotteryModalityBuilder.get_lottery_modality(LotteryModality.from_string(lottery_modality))
        if modality is None:
            return None

        return (
            f"//div[contains(@class,'new-card-modalidades')][.//h2[normalize-space()='{modality}']]"
            "//button[contains(@class,'btn-compre-ja-new-card-modalidade')]"
        )
    
    # Confirmar pagamento
    @staticmethod
    def mercado_pago_card_icon(credit_card_last_digits: str) -> str:
        return f"//div[@id='mercadoPago']//span[contains(@class,'icon-cartao') and contains(@class,'glyphicon-chevron-right')]/ancestor::tr//preceding-sibling::td//h4[contains(normalize-space(.), '{credit_card_last_digits}')]" 


    # Finalizar aposta
    @staticmethod
    def purchase_details_value(purchase_details: str) -> str:
        return f"//div[contains(@class,'cabecalho_compra_detalhada')]//div[contains(normalize-space(.), '{purchase_details}')]/span/b"
    
    # Finalizar aposta
    @staticmethod
    def purchase_totals_value(purchase_totals: str) -> str:
        return f"//div[contains(@class,'totais_compra_detalhada')]//div[contains(normalize-space(.), '{purchase_totals}')]/ancestor::div[contains(@class,'float-left')]/following-sibling::div[contains(@class,'float-right')][1]//strong"
