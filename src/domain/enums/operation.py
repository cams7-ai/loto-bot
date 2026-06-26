from __future__ import annotations

from enum import StrEnum

class Operation(StrEnum):
    UNKNOWN_OPERATION = "Operação não identificada"
    START_SESSION = "Inicia sessão"
    END_SESSION = "Fecha sessão"
    ACCESS_LOTTERY_PORTAL = "Acessa o site Loterias Online CAIXA"
    ACCEPT_TERMS = "Aceita os termos de uso"
    ACCESS_HOME = "Home"
    SUBMIT_CPF = "Informa o CPF"
    REQUEST_VALIDATION_CODE = "Solicita o código de acesso"
    SUBMIT_VALIDATION_CODE = "Informa o código de acesso"
    SUBMIT_PASSWORD = "Informa a senha"
    SELECT_LOTTERY_MODALITY = "Seleciona uma modalidade"
    SHOPPING_CART = "Carrinho de compras"
    CHOOSE_RANDOM_NUMBERS = "Escolhe os números da aposta"
    ADD_BET_TO_CART = "Adiciona a aposta ao carrinho"
    CONFIRM_PURCHASE = "Confirma a compra"
    SELECT_PAYMENT_METHOD = "Seleciona PIX ou cartão"
    CONFIRM_PAYMENT = "Confirma o pagamento"
    COMPLETE_BET = "Finaliza a aposta"

    @staticmethod
    def executed_operation(operation: Operation) -> dict[str, str]:
        return {"executed_operation": operation.value}