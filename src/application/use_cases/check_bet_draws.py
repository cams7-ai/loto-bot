from __future__ import annotations

from application.dto import CheckBetDrawsCommand, CheckBetDrawsResult, PlacedBetResult, PortalBetResult
from application.ports import NotificationPort
from application.use_cases.list_placed_bets import ListPlacedBetsUseCase
from application.use_cases.list_portal_bets import ListPortalBetsUseCase
from domain import (
    AutomationError,
    AutomationSession,
    ExternalServiceError,
    LotteryModality,
    NotificationChannel,
    Operation,
)

BetCorrelationKey = tuple[str, tuple[str, ...], str]


class CheckBetDrawsUseCase:
    def __init__(
        self,
        session: AutomationSession,
        list_placed_bets: ListPlacedBetsUseCase,
        list_portal_bets: ListPortalBetsUseCase,
        notifier: NotificationPort,
    ) -> None:
        self._session = session
        self._list_placed_bets = list_placed_bets
        self._list_portal_bets = list_portal_bets
        self._notifier = notifier

    def run(self, command: CheckBetDrawsCommand) -> CheckBetDrawsResult:
        placed_bets = self._list_placed_bets.run(command.history_filters)
        if not placed_bets:
            return self._no_matches_result()

        portal_bets = self._list_portal_bets.run(command.portal_filters)
        matches = self.correlate(placed_bets, portal_bets)
        if not matches:
            return self._no_matches_result()

        self._session.mark_running(Operation.CHECK_BET_DRAWS)
        try:
            channel = self._notifier.notify_draw_results(self._session, matches)
            if channel is NotificationChannel.NONE:
                raise ExternalServiceError(
                    "Nenhum canal confirmou o envio da notificação.",
                    operation=Operation.CHECK_BET_DRAWS,
                )
        except AutomationError:
            self._session.mark_failed(Operation.CHECK_BET_DRAWS)
            raise
        except Exception as exc:
            self._session.mark_failed(Operation.CHECK_BET_DRAWS)
            raise ExternalServiceError(
                "Não foi possível enviar a notificação da conferência.",
                operation=Operation.CHECK_BET_DRAWS,
            ) from exc

        self._session.mark_ready()
        return CheckBetDrawsResult(
            matched_bets=len(matches),
            notification_sent=True,
            notification_channel=channel,
            message=self._notification_message(channel),
        )

    @classmethod
    def correlate(
        cls,
        placed_bets: list[PlacedBetResult],
        portal_bets: list[PortalBetResult],
    ) -> list[PortalBetResult]:
        placed_keys = {cls._placed_bet_key(bet) for bet in placed_bets}
        return [bet for bet in portal_bets if cls._portal_bet_key(bet) in placed_keys]

    @classmethod
    def _placed_bet_key(cls, bet: PlacedBetResult) -> BetCorrelationKey:
        return cls._key(bet.lottery_modality.name, bet.selected_numbers, bet.draw_number)

    @classmethod
    def _portal_bet_key(cls, bet: PortalBetResult) -> BetCorrelationKey:
        modality = bet.lottery_modality
        modality_name = modality.name if isinstance(modality, LotteryModality) else modality.strip()
        return cls._key(modality_name, bet.selected_numbers, bet.draw_number)

    @staticmethod
    def _key(modality: str, selected_numbers: list[str], draw_number: str) -> BetCorrelationKey:
        return (
            modality.strip(),
            tuple(str(number).strip() for number in selected_numbers),
            str(draw_number).strip(),
        )

    @staticmethod
    def _notification_message(channel: NotificationChannel) -> str:
        if channel is NotificationChannel.WHATSAPP:
            return "Conferência concluída e notificação enviada pelo WhatsApp."
        return "Conferência concluída e notificação enviada por e-mail."

    @staticmethod
    def _no_matches_result() -> CheckBetDrawsResult:
        return CheckBetDrawsResult(
            matched_bets=0,
            notification_sent=False,
            notification_channel=NotificationChannel.NONE,
            message="Conferência concluída. Nenhuma aposta correspondente foi encontrada.",
        )
