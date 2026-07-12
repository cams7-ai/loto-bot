from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Bet:
    numbers: list[str]
    draw: str
    status: str
    amount: str
