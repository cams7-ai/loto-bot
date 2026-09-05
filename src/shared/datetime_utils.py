from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from shared.constants import SAO_PAULO_TIMEZONE


def sao_paulo_timezone() -> ZoneInfo:
    return ZoneInfo(SAO_PAULO_TIMEZONE)


def with_sao_paulo_timezone(value: datetime, *, remove_microseconds: bool = False) -> datetime:
    result = (
        value.replace(tzinfo=sao_paulo_timezone()) if value.tzinfo is None else value.astimezone(sao_paulo_timezone())
    )

    if remove_microseconds:
        return result.replace(microsecond=0)
    return result


def with_utc(
    value: datetime,
    remove_microseconds: bool = False,
) -> datetime:
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    if remove_microseconds:
        value = value.replace(microsecond=0)

    return value


def format_with_sao_paulo_timezone(value: datetime) -> str:
    return value.replace(
        tzinfo=sao_paulo_timezone(),
        microsecond=0,
    ).isoformat(timespec="seconds")


def parse_sao_paulo_datetime(date_value: str, time_value: str, date_format: str = "%d/%m/%Y %H:%M:%S") -> datetime:
    return datetime.strptime(f"{date_value} {time_value}", date_format).replace(tzinfo=sao_paulo_timezone())
