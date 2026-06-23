from domain import Operation, ErrorCode

from application.notification.error_message_builder import ErrorMessageBuilder

class NotificationMessageBuilder:

    @staticmethod
    def build_email_message() -> str:
        return (
            "A operação não pôde ser concluída neste momento.<br><br>"
            "Recomendamos tentar novamente em alguns minutos.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def build_whatsapp_message(operation: Operation, error_code: ErrorCode) -> str:
        return (
            f"❌ {ErrorMessageBuilder.get_error_message(error_code)}.\n\n"
            f"Etapa: {operation.value}\n\n"
            "A operação não pôde ser concluída neste momento. "
            "Tente novamente em alguns minutos."
        )