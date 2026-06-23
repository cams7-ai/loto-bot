import re

from domain import Operation


class PlaywrightErrorMessageBuilder:
    _UNKNOWN_VALUE = "Não identificado"

    @staticmethod
    def build_error_message(
        operation: Operation,
        error_message: str,
    ) -> str:
        element = PlaywrightErrorMessageBuilder._extract_element(error_message)

        if element == PlaywrightErrorMessageBuilder._UNKNOWN_VALUE:
            return error_message

        event = PlaywrightErrorMessageBuilder._extract_event(error_message)
        cause = PlaywrightErrorMessageBuilder._extract_cause(error_message)

        return (
            f"Falha ao executar a operação '{operation.value}'. "
            f"Evento '{event}' no elemento {element}. "
            f"Motivo: {cause}."
        )

    @staticmethod
    def _extract_event(error_message: str) -> str:
        match = re.search(r"^(Locator\.\w+):", error_message)
        return (
            match.group(1)
            if match
            else PlaywrightErrorMessageBuilder._UNKNOWN_VALUE
        )

    @staticmethod
    def _extract_element(error_message: str) -> str:
        match = re.search(r"locator\((.*?)\)", error_message, re.DOTALL)
        return (
            match.group(1)
            if match
            else PlaywrightErrorMessageBuilder._UNKNOWN_VALUE
        )

    @staticmethod
    def _extract_cause(error_message: str) -> str:
        match = re.search(r":\s*(.+?)\.", error_message)
        return (
            match.group(1)
            if match
            else PlaywrightErrorMessageBuilder._UNKNOWN_VALUE
        )