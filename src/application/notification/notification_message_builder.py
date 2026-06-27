from domain import Operation, ErrorCode

from domain import AutomationError
from application.notification.error_message_builder import ErrorMessageBuilder

class NotificationMessageBuilder:

    @staticmethod
    def build_email_message(error_message: str) -> str:
        return (
            f"{error_message}.<br><br>"
            "Por favor, verifique e tente novamente.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def build_whatsapp_message(error: AutomationError) -> str:
        return (
            f"❌ {ErrorMessageBuilder.get_error_message(error.code)}.\n\n"
            f"Etapa: {error.operation.value}\n\n"
            f"{str(error)}. "
            "Por favor, verifique e tente novamente."
        )

