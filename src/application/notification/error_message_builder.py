from domain import Operation, ErrorCode

class ErrorMessageBuilder:

    @staticmethod
    def get_error_message(error_code: ErrorCode) -> str:
        messages = {
            ErrorCode.BAD_REQUEST: "Requisição inválida",
            ErrorCode.NOT_FOUND: "Rota não encontrada",
            ErrorCode.METHOD_NOT_ALLOWED: "Método não permitido",
            ErrorCode.INTERNAL_SERVER_ERROR: "Erro interno",
            ErrorCode.AUTOMATION_ERROR_CODE: "Falha na automação",
            ErrorCode.EXTERNAL_SERVICE_ERROR_CODE: "Serviço externo indisponível",
            ErrorCode.BROWSER_SESSION_OPEN_ERROR_CODE: "Sessão já aberta",
            ErrorCode.BROWSER_SESSION_CLOSED_ERROR_CODE: "Sessão fechada",           
            ErrorCode.INVALID_CPF_ERROR_CODE: "O CPF é inválido",
            ErrorCode.INVALID_PASSWORD_ERROR_CODE: "A senha é inválida",
            ErrorCode.PAYMENT_CONFIRMATION_DISABLED_ERROR_CODE: "Confirmação de pagamento desabilitada",
        }

        return messages.get(error_code, "Erro desconhecido")