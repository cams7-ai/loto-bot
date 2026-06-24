"""Gateway composto para notificações por WhatsApp e e-mail."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application import get_error_message, NotificationPort
from domain import (
    Operation,
    ErrorCode,
    AutomationSession,
    WhatsAppSessionStatus,
    WhatsAppMessageStatus,
)
from infrastructure.clients.mail_sender_client import MailSenderClient
from infrastructure.clients.whatsapp_notify_client import WhatsAppNotifyClient

logger = logging.getLogger(__name__)


class NotificationGateway(NotificationPort):
    _TIMEZONE = "America/Sao_Paulo"

    def __init__(
        self,
        whatsapp: WhatsAppNotifyClient,
        mail: MailSenderClient,
        whatsapp_enabled: bool = False,
    ) -> None:
        self._whatsapp = whatsapp
        self._mail = mail
        self._whatsapp_enabled = whatsapp_enabled

    def start_whatsapp_session(self, session: AutomationSession) -> None:
        operation = session.executed_operation
        if not self._whatsapp_enabled:
            session.whatsapp_enabled = False
            logger.info("Integração com WhatsApp desabilitada", Operation.executed_operation(operation))
            return

        try:
            status = self._whatsapp.start_session(operation)
            session.whatsapp_enabled = True
            logger.info("Sessão do WhatsApp Web iniciada: %s", status, extra=Operation.executed_operation(operation))
        except Exception as exc:
            session.whatsapp_enabled = False
            logger.warning("Sessão do WhatsApp Web não inicializada: %s", exc, extra=Operation.executed_operation(operation))

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        operation = session.executed_operation
        if not session.whatsapp_enabled:
            return
        try:
            self._whatsapp.stop_session(operation)
            logger.info("Sessão do WhatsApp Web encerrada", extra=Operation.executed_operation(operation))
        except Exception as exc:
            logger.warning("Sessão do WhatsApp Web não encerrada: %s", exc, extra=Operation.executed_operation(operation))
        finally:
            session.whatsapp_enabled = False

    def notify_failure(self, session: AutomationSession, error_code: ErrorCode, whatsapp_message: str, mail_message: str) -> bool:
        operation = session.executed_operation
        if session.whatsapp_enabled:
            try:
                status = self._whatsapp.status(operation)
                response = self._whatsapp.send_message(operation, whatsapp_message) if status == WhatsAppSessionStatus.SESSION_OPEN.value else None
                if response == WhatsAppMessageStatus.SENT.value:
                    logger.info("Notificação enviada pelo WhatsApp", extra=Operation.executed_operation(operation))
                    return True
            except Exception as exc:
                logger.warning("Falha ao enviar WhatsApp: %s", exc, extra=Operation.executed_operation(operation))

        self._send_mail_fallback(session, error_code, mail_message)
        return False

    def _send_mail_fallback(self, session: AutomationSession, error_code: ErrorCode, message: str) -> None:
        operation = session.executed_operation
        try:
            timestamp_timezone = ZoneInfo(self._TIMEZONE)
        except ZoneInfoNotFoundError:  # pragma: no cover - depends on host timezone database.
            logger.warning("Timezone %s indisponível; usando UTC-03:00", self._TIMEZONE, extra=Operation.executed_operation(operation))
            timestamp_timezone = timezone(timedelta(hours=-3), name=self._TIMEZONE)

        now = datetime.now(timestamp_timezone).strftime("%d/%m/%Y %H:%M:%S")
        subject = f"LotoBot - falha durante {operation.value}"
        body = (
            "<html><body>"
            f"<h1>{get_error_message(error_code)}</h1>"
            f"<p><strong>Operação:</strong> {operation.value}</p>"
            f"<p><strong>Data/hora:</strong> {now}</p>"
            f"<p>{message}</p>"
            "</body></html>"
        )
        try:
            self._mail.send(operation, subject, body)
            logger.info("E-mail de fallback enviado", extra=Operation.executed_operation(operation))
        except Exception as exc:
            logger.error("Erro ao enviar e-mail de fallback: %s", exc, extra=Operation.executed_operation(operation))
