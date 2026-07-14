from domain import ErrorCode


class ErrorMessageBuilder:
    @staticmethod
    def get_error_message(error_code: ErrorCode) -> str:
        messages = {
            ErrorCode.BAD_REQUEST: "Requisição inválida",
            ErrorCode.NOT_FOUND: "Rota não encontrada",
            ErrorCode.METHOD_NOT_ALLOWED: "Método não permitido",
            ErrorCode.INTERNAL_SERVER_ERROR: "Erro interno",
            ErrorCode.AUTOMATION_ERROR_CODE: "Falha na automação",
            ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE: "Sessão já aberta",
            ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE: "Sessão fechada",
            ErrorCode.PAGE_REDIRECTION_ERROR_CODE: "Erro no redirecionamento da página",
            ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE: "Confirmação de pagamento desabilitada",
            ErrorCode.EXTERNAL_SERVICE_ERROR_CODE: "Serviço externo indisponível",
            ErrorCode.INVALID_CPF_ERROR_CODE: "O CPF é inválido",
            ErrorCode.INVALID_PASSWORD_ERROR_CODE: "A senha é inválida",
            ErrorCode.INDIVIDUAL_BET_REGISTRATION_CLOSED_ERROR_CODE: "Registro de apostas indisponível",
            ErrorCode.BET_TEMPORARILY_DISABLED_ERROR_CODE: "Aposta temporariamente desabilitada",
            ErrorCode.DAILY_PURCHASE_LIMIT_ERROR_CODE: "Limite máximo diário de compras atingido",
            ErrorCode.BETS_NOT_AVAILABLE_FOR_CAPTURE_ERROR_CODE: "Apostas não disponíveis para captura",
        }

        return messages.get(error_code, "Erro desconhecido")
