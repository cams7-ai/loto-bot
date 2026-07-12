from application.notification.error_message_builder import ErrorMessageBuilder
from domain import AutomationError


class NotificationMessageBuilder:
    @staticmethod
    def build_email_message(error_message: str) -> str:
        return (
            f"{error_message}.<br><br>"
            "Por favor, verifique e tente novamente.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def build_whatsapp_message(exc: AutomationError) -> str:
        return (
            f"❌ {ErrorMessageBuilder.get_error_message(exc.code)}.\n\n"
            f"Etapa: {exc.operation.value}\n\n"
            f"{str(exc)}. "
            "Por favor, verifique e tente novamente."
        )
