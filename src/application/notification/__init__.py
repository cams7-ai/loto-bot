from application.notification.error_message_builder import ErrorMessageBuilder
from application.notification.notification_message_builder import NotificationMessageBuilder

build_error_email_message = NotificationMessageBuilder.build_error_email_message
build_success_email_message = NotificationMessageBuilder.build_success_email_message
build_success_whatsapp_message = NotificationMessageBuilder.build_success_whatsapp_message
build_error_whatsapp_message = NotificationMessageBuilder.build_error_whatsapp_message
get_error_message = ErrorMessageBuilder.get_error_message

__all__ = [
    "build_error_email_message",
    "build_success_email_message",
    "build_success_whatsapp_message",
    "build_error_whatsapp_message",
    "get_error_message",
]
