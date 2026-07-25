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


PORTAL_RELATIVE_PERIOD_ALIASES = {
    PortalBetRelativePeriod.LAST_7_DAYS.value: PortalBetRelativePeriod.LAST_7_DAYS,
    "ultimos 7 dias": PortalBetRelativePeriod.LAST_7_DAYS,
    PortalBetRelativePeriod.LAST_15_DAYS.value: PortalBetRelativePeriod.LAST_15_DAYS,
    "ultimos 15 dias": PortalBetRelativePeriod.LAST_15_DAYS,
    PortalBetRelativePeriod.LAST_30_DAYS.value: PortalBetRelativePeriod.LAST_30_DAYS,
    "ultimos 30 dias": PortalBetRelativePeriod.LAST_30_DAYS,
    PortalBetRelativePeriod.LAST_45_DAYS.value: PortalBetRelativePeriod.LAST_45_DAYS,
    "ultimos 45 dias": PortalBetRelativePeriod.LAST_45_DAYS,
    PortalBetRelativePeriod.LAST_90_DAYS.value: PortalBetRelativePeriod.LAST_90_DAYS,
    "ultimos 90 dias": PortalBetRelativePeriod.LAST_90_DAYS,
}


PORTAL_LOTTERY_MODALITY_ALIASES = {
    "todas": None,
    "dia de sorte": LotteryModality.DIA_DE_SORTE,
    "dupla sena": LotteryModality.DUPLA_SENA,
    "loteca": LotteryModality.LOTECA,
    "lotofacil": LotteryModality.LOTOFACIL,
    "lotomania": LotteryModality.LOTOMANIA,
    "+milionaria": LotteryModality.MAIS_MILIONARIA,
    "mega-sena": LotteryModality.MEGA_SENA,
    "quina": LotteryModality.QUINA,
    "super sete": LotteryModality.SUPER_SETE,
    "timemania": LotteryModality.TIMEMANIA,
}

UNSUPPORTED_PORTAL_MODALITIES = {
    LotteryModality.QUINA_ESPECIAL,
    LotteryModality.LOTECA_ESPECIAL,
    LotteryModality.LOTOFACIL_ESPECIAL,
}


def normalize_public_value(value: str) -> str:
    stripped = " ".join(value.strip().split()).casefold()
    return "".join(
        character for character in unicodedata.normalize("NFD", stripped) if unicodedata.category(character) != "Mn"
    )


def parse_catalog_value[T: Enum](parameter: str, value: str | None, enum_type: type[T]) -> T | None:
    if value is None:
        return None
    normalized = normalize_public_value(value)
    try:
        return enum_type(normalized)
    except ValueError:
        allowed = ", ".join(str(member.value) for member in enum_type)
        raise ValueError(f"Parâmetro {parameter} inválido. Valores permitidos: {allowed}.") from None


def allowed_catalog_values(enum_type: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_type]


def invalid_catalog_detail(parameter: str, value: str, enum_type: type[Enum]) -> ValidationErrorDetail:
    return ValidationErrorDetail(
        field=parameter,
        rejected_value=value,
        allowed_values=allowed_catalog_values(enum_type),
        message=INVALID_VALUE_MESSAGE,
    )


def parse_portal_lottery_modality(value: str | None) -> LotteryModality | None:
    if value is None:
        return None
    if value in LotteryModality.__members__:
        modality = LotteryModality[value]
        if modality in UNSUPPORTED_PORTAL_MODALITIES:
            raise ValueError("Parâmetro lottery_modality inválido para consulta ao portal.")
        return modality
    normalized = normalize_public_value(value)
    if normalized == ALL:
        return None
    if normalized in PORTAL_LOTTERY_MODALITY_ALIASES:
        return PORTAL_LOTTERY_MODALITY_ALIASES[normalized]
    allowed = ", ".join(LOTTERY_MODALITY_ALLOWED_VALUES)
    raise ValueError(f"Parâmetro lottery_modality inválido. Valores permitidos: {allowed}.")


def parse_public_lottery_modality(value: str | None) -> LotteryModality | None:
    if value is None:
        return None
    if value in LotteryModality.__members__:
        return LotteryModality[value]
    normalized = normalize_public_value(value)
    if normalized == ALL:
        return None
    resolved_by_value = LotteryModality.from_string(normalized)
    if resolved_by_value is not None:
        return resolved_by_value
    if normalized in PORTAL_LOTTERY_MODALITY_ALIASES:
        return PORTAL_LOTTERY_MODALITY_ALIASES[normalized]
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
    normalized = normalize_public_value(value)
    if normalized in PORTAL_RELATIVE_PERIOD_ALIASES:
        return PORTAL_RELATIVE_PERIOD_ALIASES[normalized]
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
    month_name = normalize_public_value(match.group(1))
    for month, label in MONTH_NAMES.items():
        if normalize_public_value(label) == month_name:
            return PortalYearMonth(year=int(match.group(2)), month=month)
    return None


def _validate_year_month_window(year_month: PortalYearMonth, today: date) -> None:
    allowed = current_and_previous_months(today)
    if year_month not in allowed:
        allowed_values = ", ".join(month.canonical_value for month in allowed)
        raise ValueError(f"Parâmetro month_year fora da janela permitida. Valores permitidos: {allowed_values}.")
