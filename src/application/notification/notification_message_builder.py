from html import escape

from application.dto import PortalBetResult, PurchaseResult
from application.notification.error_message_builder import ErrorMessageBuilder
from domain import AutomationError, BrlCurrencyFormatter, LotteryModality
from shared import with_sao_paulo_timezone


class NotificationMessageBuilder:
    DRAW_RESULTS_SUBJECT = "LotoBot - resultado da conferência de apostas"

    @staticmethod
    def build_error_email_message(error_message: str) -> str:
        return (
            f"{error_message}.<br><br>"
            "Por favor, verifique e tente novamente.<br><br>"
            "Caso o problema persista, entre em contato com o suporte."
        )

    @staticmethod
    def build_error_whatsapp_message(exc: AutomationError) -> str:
        return (
            f"❌ {ErrorMessageBuilder.get_error_message(exc.code)}.\n\n"
            f"Etapa: {exc.operation.value}\n\n"
            f"{str(exc)}. "
            "Por favor, verifique e tente novamente."
        )

    @staticmethod
    def build_success_email_message(purchase: PurchaseResult) -> str:
        bets = "".join(
            "<li>"
            f"Números: {', '.join(bet.numbers)} | "
            f"Concurso: {bet.draw} | "
            f"Situação: {bet.status} | "
            f"Valor: {BrlCurrencyFormatter.format_brl_currency(bet.amount)}"
            "</li>"
            for bet in purchase.bets
        )
        return (
            "<html><body>"
            "<h1>Aposta finalizada com sucesso</h1>"
            f"<p><strong>Modalidade:</strong> {purchase.lottery_modality or '-'}</p>"
            f"<p><strong>Número da compra:</strong> {purchase.purchase_number}</p>"
            f"<p><strong>Data/hora da compra:</strong> {purchase.purchase_datetime.strftime('%d/%m/%Y %H:%M:%S')}</p>"
            f"<p><strong>Total da compra:</strong> "
            f"{BrlCurrencyFormatter.format_brl_currency(purchase.total_purchase)}</p>"
            "<p><strong>Total de apostas efetivadas:</strong> "
            f"{BrlCurrencyFormatter.format_brl_currency(purchase.total_bets_effective)}</p>"
            f"<h2>Apostas</h2><ul>{bets}</ul>"
            "</body></html>"
        )

    @staticmethod
    def build_success_whatsapp_message(purchase: PurchaseResult) -> str:
        first_bet = purchase.bets[0] if purchase.bets else None
        bet_summary = ""
        if first_bet is not None:
            bet_summary = (
                f"\nNúmeros: {', '.join(first_bet.numbers)}"
                f"\nConcurso: {first_bet.draw}"
                f"\nSituação: {first_bet.status}"
                f"\nValor: {BrlCurrencyFormatter.format_brl_currency(first_bet.amount)}"
            )

        return (
            "✅ Aposta finalizada com sucesso.\n\n"
            f"Modalidade: {purchase.lottery_modality or '-'}"
            f"{bet_summary}\n"
            f"Número da compra: {purchase.purchase_number}\n"
            f"Total da compra: {BrlCurrencyFormatter.format_brl_currency(purchase.total_purchase)}\n"
            f"Total efetivado: {BrlCurrencyFormatter.format_brl_currency(purchase.total_bets_effective)}"
        )

    @classmethod
    def build_draw_results_whatsapp_message(cls, bets: list[PortalBetResult]) -> str:
        blocks = [cls._draw_result_text(bet) for bet in bets]
        return "🔎 Resultado da conferência de apostas\n\n" + "\n\n---\n\n".join(blocks)

    @classmethod
    def build_draw_results_email_message(cls, bets: list[PortalBetResult]) -> str:
        blocks = "".join(
            "<section>"
            f"<p><strong>Data/hora da compra:</strong> {escape(cls._purchase_datetime(bet))}</p>"
            f"<p><strong>Modalidade:</strong> {escape(cls._lottery_modality(bet))}</p>"
            f"<p><strong>Números selecionados:</strong> "
            f"{escape(', '.join(str(number) for number in bet.selected_numbers))}</p>"
            f"<p><strong>Concurso:</strong> {escape(str(bet.draw_number))}</p>"
            f"<p><strong>Situação:</strong> {escape(str(bet.status))}</p>"
            "</section>"
            for bet in bets
        )
        return f"<html><body><h1>Resultado da conferência de apostas</h1>{blocks}</body></html>"

    @classmethod
    def _draw_result_text(cls, bet: PortalBetResult) -> str:
        return (
            f"Data/hora da compra: {cls._purchase_datetime(bet)}\n"
            f"Modalidade: {cls._lottery_modality(bet)}\n"
            f"Números selecionados: {', '.join(str(number) for number in bet.selected_numbers)}\n"
            f"Concurso: {bet.draw_number}\n"
            f"Situação: {bet.status}"
        )

    @staticmethod
    def _purchase_datetime(bet: PortalBetResult) -> str:
        purchase_datetime = with_sao_paulo_timezone(bet.purchase_datetime, remove_microseconds=True)
        return purchase_datetime.strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _lottery_modality(bet: PortalBetResult) -> str:
        if isinstance(bet.lottery_modality, LotteryModality):
            return bet.lottery_modality.name
        return str(bet.lottery_modality)
