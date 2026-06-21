"""Porta para leitura do código de validação."""

from __future__ import annotations

from typing import Protocol
from domain import Operation

class ValidationCodePort(Protocol):
    def get_validation_code(self, operation: Operation) -> str:
        """Busca o código de validação recebido por e-mail."""
