from __future__ import annotations

import re
import unicodedata
from datetime import date
from enum import Enum

from application.exceptions import ValidationErrorDetail
from domain import LotteryModality
from domain.enums import (
    PortalBetRelativePeriod,
    PortalYearMonth,
)

MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

ALL = "all"
INVALID_VALUE_MESSAGE = "Valor inválido."
INVALID_MONTH_YEAR_MESSAGE = "Valor inválido. Utilize o formato YYYY-MM ou um período relativo válido."
INVALID_DATE_MESSAGE = "Valor inválido. Utilize o formato YYYY-MM-DD."
INVALID_DRAW_NUMBER_MESSAGE = "Valor inválido. Informe número maior que zero."

LOTTERY_MODALITY_ALLOWED_VALUES = [ALL, *LotteryModality.__members__]


def parse_catalog_value[T: Enum](parameter: str, value: str | None, enum_type: type[T]) -> T | None:
    if value is None:
        return None

    stripped = value.strip()
    if stripped in enum_type.__members__:
        return enum_type[stripped]
    for member in enum_type:
        if stripped == _public_catalog_value(member):
            return member

    allowed = ", ".join(_allowed_catalog_values(enum_type))
    raise ValueError(f"Parâmetro {parameter} inválido. Valores permitidos: {allowed}.") from None


def invalid_catalog_detail(parameter: str, value: str, enum_type: type[Enum]) -> ValidationErrorDetail:
    return ValidationErrorDetail(
        field=parameter,
        rejected_value=value,
        allowed_values=_allowed_catalog_values(enum_type),
        message=INVALID_VALUE_MESSAGE,
    )


def _allowed_catalog_values(enum_type: type[Enum]) -> list[str]:
    return [_public_catalog_value(member) for member in enum_type]


def _public_catalog_value(member: Enum) -> str:
    return member.name.lower().replace("_", "-")


def parse_portal_lottery_modality(value: str | None) -> LotteryModality | None:
    if value is None:
        return None
    stripped = value.strip()
    if stripped in LotteryModality.__members__:
        return LotteryModality[stripped]
    if stripped == ALL or stripped == ALL.upper():
        return None

    normalized_value = _normalize_lottery_modality_value(stripped)
    if _normalize_lottery_modality_value(ALL) == normalized_value:
        return None
    for modality in LotteryModality:
        if normalized_value in {
            _normalize_lottery_modality_value(modality.name),
            _normalize_lottery_modality_value(modality.value),
        }:
            return modality

    allowed = ", ".join(LOTTERY_MODALITY_ALLOWED_VALUES)
    raise ValueError(f"Parâmetro lottery_modality inválido. Valores permitidos: {allowed}.")


def invalid_lottery_modality_detail(parameter: str, value: str) -> ValidationErrorDetail:
    return ValidationErrorDetail(
        field=parameter,
        rejected_value=value,
        allowed_values=list(LOTTERY_MODALITY_ALLOWED_VALUES),
        message=INVALID_VALUE_MESSAGE,
    )


def parse_portal_month_year(value: str | None, today: date) -> PortalBetRelativePeriod | PortalYearMonth | None:
    if value is None:
        return None

    if value in PortalBetRelativePeriod.__members__:
        return PortalBetRelativePeriod[value]

    year_month = _parse_year_month(value)
    _validate_year_month_window(year_month, today)
    return year_month


def invalid_month_year_detail(value: str, today: date) -> ValidationErrorDetail:
    try:
        year_month = _parse_year_month(value)
        _validate_year_month_window(year_month, today)
    except ValueError as exc:
        if "fora da janela" in str(exc):
            return ValidationErrorDetail(
                field="month_year",
                rejected_value=value,
                allowed_values=[month.canonical_value for month in current_and_previous_months(today)],
                message=INVALID_VALUE_MESSAGE,
            )
    return ValidationErrorDetail(
        field="month_year",
        rejected_value=value,
        message=INVALID_MONTH_YEAR_MESSAGE,
    )


def parse_positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped.isdecimal():
        raise ValueError(INVALID_DRAW_NUMBER_MESSAGE)
    parsed = int(stripped)
    if parsed <= 0:
        raise ValueError(INVALID_DRAW_NUMBER_MESSAGE)
    return parsed


def portal_year_month_label(year_month: PortalYearMonth) -> str:
    return f"{MONTH_NAMES[year_month.month]}/{year_month.year:04d}"


def current_and_previous_months(today: date, quantity: int = 6) -> tuple[PortalYearMonth, ...]:
    year = today.year
    month = today.month
    months = []
    for _ in range(quantity):
        months.append(PortalYearMonth(year=year, month=month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return tuple(months)


def _parse_year_month(value: str) -> PortalYearMonth:
    stripped = value.strip()
    localized = _parse_localized_month(stripped)
    if localized is not None:
        return localized
    match = re.fullmatch(r"(\d{4})-(\d{2})", stripped)
    if match is None:
        raise ValueError("Parâmetro month_year inválido. Use YYYY-MM ou um período relativo permitido.")
    year = int(match.group(1))
    month = int(match.group(2))
    if month < 1 or month > 12:
        raise ValueError("Parâmetro month_year inválido. O mês deve estar entre 01 e 12.")
    return PortalYearMonth(year=year, month=month)


def _parse_localized_month(value: str) -> PortalYearMonth | None:
    match = re.fullmatch(r"([^/]+)/(\d{4})", value)
    if match is None:
        return None
    month_name = _normalize_public_value(match.group(1))
    for month, label in MONTH_NAMES.items():
        if _normalize_public_value(label) == month_name:
            return PortalYearMonth(year=int(match.group(2)), month=month)
    return None


def _validate_year_month_window(year_month: PortalYearMonth, today: date) -> None:
    allowed = current_and_previous_months(today)
    if year_month not in allowed:
        allowed_values = ", ".join(month.canonical_value for month in allowed)
        raise ValueError(f"Parâmetro month_year fora da janela permitida. Valores permitidos: {allowed_values}.")


def _normalize_public_value(value: str) -> str:
    stripped = " ".join(value.strip().split()).casefold()
    return "".join(
        character for character in unicodedata.normalize("NFD", stripped) if unicodedata.category(character) != "Mn"
    )


def _normalize_lottery_modality_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _normalize_public_value(value))
