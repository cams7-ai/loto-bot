"""Gateway composto para notificações por WhatsApp e e-mail."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.ports import NotificationPort
from domain import Operation, AutomationSession
from infrastructure.clients.mail_sender_client import MailSenderClient
from infrastructure.clients.whatsapp_notify_client import WhatsAppNotifyClient

logger = logging.getLogger(__name__)


class NotificationGateway(NotificationPort):
    def __init__(
        self,
        whatsapp: WhatsAppNotifyClient,
        mail: MailSenderClient,
        timezone_name: str = "America/Sao_Paulo",
        whatsapp_enabled: bool = True,
    ) -> None:
        self._whatsapp = whatsapp
        self._mail = mail
        self._timezone_name = timezone_name
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

    def notify_failure(self, session: AutomationSession, message: str) -> None:
        operation = session.executed_operation
        if session.whatsapp_enabled:
            try:
                status = self._whatsapp.status(operation)
                if status == "SESSAO_ABERTA" and self._whatsapp.send_message(message) == "enviado":
                    logger.info("Notificação enviada pelo WhatsApp", extra=Operation.executed_operation(operation))
                    return
            except Exception as exc:
                logger.warning("Falha ao enviar WhatsApp: %s", exc, extra=Operation.executed_operation(operation))

        self._send_mail_fallback(session, message)

    def _send_mail_fallback(self, session: AutomationSession, message: str) -> None:
        operation = session.executed_operation
        try:
            timestamp_timezone = ZoneInfo(self._timezone_name)
        except ZoneInfoNotFoundError:  # pragma: no cover - depends on host timezone database.
            logger.warning("Timezone %s indisponível; usando UTC-03:00", self._timezone_name, extra=Operation.executed_operation(operation))
            timestamp_timezone = timezone(timedelta(hours=-3), name="America/Sao_Paulo")

        now = datetime.now(timestamp_timezone).isoformat()
        subject = f"LotoBot - falha durante {operation.value}"
        body = (
            "<html><body>"
            "<h1>Falha na automação LotoBot</h1>"
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
