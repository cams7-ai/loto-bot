import re

from domain import Operation


class PlaywrightErrorMessageBuilder:
    _UNKNOWN_VALUE = "Não identificado"

    @classmethod
    def build_error_message(
        cls,
        operation: Operation,
        error_message: str,
    ) -> str:
        element = cls._extract_element(error_message)

        if element == cls._UNKNOWN_VALUE:
            return error_message

        event = cls._extract_event(error_message)
        cause = cls._extract_cause(error_message)

        return (
            f"Falha ao executar a operação '{operation.value}'. "
            f"Evento '{event}' no elemento {element}. "
            f"Motivo: {cause}."
        )

    @classmethod
    def _extract_event(cls, error_message: str) -> str:
        match = re.search(r"^(Locator\.\w+):", error_message)
        return (
            match.group(1)
            if match
            else cls._UNKNOWN_VALUE
        )

    @classmethod
    def _extract_element(cls, error_message: str) -> str:
        match = re.search(r"locator\((['\"])(.*?)(?<!\\)\1\)", error_message, re.DOTALL)
        return (
            f"{match.group(1)}{match.group(2)}{match.group(1)}"
            if match
            else cls._UNKNOWN_VALUE
        )

    @classmethod
    def _extract_cause(cls, error_message: str) -> str:
        match = re.search(r":\s*(.+?)\.", error_message)
        return (
            match.group(1)
            if match
            else cls._UNKNOWN_VALUE
        )
