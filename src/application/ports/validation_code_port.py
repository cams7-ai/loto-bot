"""Porta para leitura do código de validação."""

from __future__ import annotations

from typing import Protocol


class ValidationCodePort(Protocol):
    def get_validation_code(self) -> str:
        """Busca o código de validação recebido por e-mail."""
