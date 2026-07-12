"""Gateway composto para notificações por WhatsApp e e-mail."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application import NotificationPort, build_email_message, build_whatsapp_message, get_error_message
from domain import AutomationError, AutomationSession, Operation, WhatsAppMessageStatus, WhatsAppSessionStatus
from infrastructure.clients.mail_sender_client import MailSenderClient
from infrastructure.clients.whatsapp_notify_client import WhatsAppNotifyClient
from shared import SAO_PAULO_TIMEZONE

logger = logging.getLogger(__name__)


class NotificationGateway(NotificationPort):
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
            logger.warning(
                "Sessão do WhatsApp Web não inicializada: %s", exc, extra=Operation.executed_operation(operation)
            )

    def stop_whatsapp_session(self, session: AutomationSession) -> None:
        operation = session.executed_operation
        if not session.whatsapp_enabled:
            return
        try:
            self._whatsapp.stop_session(operation)
            logger.info("Sessão do WhatsApp Web encerrada", extra=Operation.executed_operation(operation))
        except Exception as exc:
            logger.warning(
                "Sessão do WhatsApp Web não encerrada: %s", exc, extra=Operation.executed_operation(operation)
            )
        finally:
            session.whatsapp_enabled = False

    def notify_failure(self, whatsapp_enabled: bool, exc: AutomationError) -> bool:
        operation = exc.operation
        if whatsapp_enabled:
            try:
                status = self._whatsapp.status(operation)
                response = (
                    self._whatsapp.send_message(operation, build_whatsapp_message(exc))
                    if status == WhatsAppSessionStatus.SESSION_OPEN.value
                    else None
                )
                if response == WhatsAppMessageStatus.SENT.value:
                    logger.info("Notificação enviada pelo WhatsApp", extra=Operation.executed_operation(operation))
                    return True
            except Exception as exc:
                logger.warning("Falha ao enviar WhatsApp: %s", exc, extra=Operation.executed_operation(operation))

        self._send_mail_fallback(exc)
        return False

    def _send_mail_fallback(self, exc: AutomationError) -> None:
        operation = exc.operation
        try:
            timestamp_timezone = ZoneInfo(SAO_PAULO_TIMEZONE)
        except ZoneInfoNotFoundError:  # pragma: no cover - depends on host timezone database.
            logger.warning(
                "Timezone %s indisponível; usando UTC-03:00",
                SAO_PAULO_TIMEZONE,
                extra=Operation.executed_operation(operation),
            )
            timestamp_timezone = timezone(timedelta(hours=-3), name=SAO_PAULO_TIMEZONE)

        now = datetime.now(timestamp_timezone).strftime("%d/%m/%Y %H:%M:%S")
        subject = f"LotoBot - falha durante {operation.value}"
        body = (
            "<html><body>"
            f"<h1>{get_error_message(exc.code)}</h1>"
            f"<p><strong>Operação:</strong> {operation.value}</p>"
            f"<p><strong>Data/hora:</strong> {now}</p>"
            f"<p>{build_email_message(str(exc))}</p>"
            "</body></html>"
        )
        try:
            self._mail.send(operation, subject, body)
            logger.info("E-mail de fallback enviado", extra=Operation.executed_operation(operation))
        except Exception as exc:
            logger.error("Erro ao enviar e-mail de fallback: %s", exc, extra=Operation.executed_operation(operation))
