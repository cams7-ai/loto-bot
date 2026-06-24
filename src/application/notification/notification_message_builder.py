from domain import Operation, ErrorCode

from application.notification.error_message_builder import ErrorMessageBuilder

class NotificationMessageBuilder:

    @staticmethod
    def build_email_message(operation: Operation, error_message: str | None = None) -> str:
        if error_message is not None:
            if operation == Operation.SUBMIT_CPF:
                return NotificationMessageBuilder._build_email_message(error_message)

            if operation == Operation.SUBMIT_PASSWORD:
                return NotificationMessageBuilder._build_email_message(error_message)

        return (
            "A operação não pôde ser concluída neste momento.<br><br>"
            "Recomendamos tentar novamente em alguns minutos.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def _build_email_message(error_message: str) -> str:
        return (
            f"{error_message}.<br><br>"
            "Por favor, verifique e tente novamente.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def build_whatsapp_message(operation: Operation, error_code: ErrorCode, error_message: str | None = None) -> str:
        if error_message is not None:
            if operation == Operation.SUBMIT_CPF:
                return NotificationMessageBuilder._build_whatsapp_message(operation, "CPF inválido", error_message)

            if operation == Operation.SUBMIT_PASSWORD:
                return NotificationMessageBuilder._build_whatsapp_message(operation, "Senha inválida", error_message)

        return (
            f"❌ {ErrorMessageBuilder.get_error_message(error_code)}.\n\n"
            f"Etapa: {operation.value}\n\n"
            "A operação não pôde ser concluída neste momento. "
            "Tente novamente em alguns minutos."
        )

    @staticmethod
    def _build_whatsapp_message(operation: Operation, title: str, error_message: str) -> str:
        return (
            f"❌ {title}.\n\n"
            f"Etapa: {operation.value}\n\n"
            f"{error_message}. "
            "Por favor, verifique e tente novamente."
        )

