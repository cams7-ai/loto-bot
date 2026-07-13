from application.dto import PurchaseResult
from application.notification.error_message_builder import ErrorMessageBuilder
from domain import AutomationError


def _format_brl_currency(value) -> str:
    amount = value or 0
    formatted_amount = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted_amount}"


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

    @staticmethod
    def build_success_email_message(purchase: PurchaseResult) -> str:
        bets = "".join(
            "<li>"
            f"Números: {', '.join(bet.numbers)} | "
            f"Concurso: {bet.draw} | "
            f"Situação: {bet.status} | "
            f"Valor: {_format_brl_currency(bet.amount)}"
            "</li>"
            for bet in purchase.bets
        )
        return (
            "<html><body>"
            "<h1>Aposta finalizada com sucesso</h1>"
            f"<p><strong>Modalidade:</strong> {purchase.lottery_modality or '-'}</p>"
            f"<p><strong>Número da compra:</strong> {purchase.purchase_details_number}</p>"
            f"<p><strong>Data/hora da compra:</strong> {purchase.purchase_details_datetime.isoformat()}</p>"
            f"<p><strong>Total da compra:</strong> {_format_brl_currency(purchase.total_purchase)}</p>"
            "<p><strong>Total de apostas efetivadas:</strong> "
            f"{_format_brl_currency(purchase.total_bets_effective)}</p>"
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
                f"\nValor: {_format_brl_currency(first_bet.amount)}"
            )

        return (
            "✅ Aposta finalizada com sucesso.\n\n"
            f"Modalidade: {purchase.lottery_modality or '-'}"
            f"{bet_summary}\n"
            f"Número da compra: {purchase.purchase_details_number}\n"
            f"Total da compra: {_format_brl_currency(purchase.total_purchase)}\n"
            f"Total efetivado: {_format_brl_currency(purchase.total_bets_effective)}"
        )
