"""Execução padronizada de etapas dos casos de uso."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from domain import AutomationSession, Operation

T = TypeVar("T")


class OperationExecutor:
    _session: AutomationSession

    def _execute(self, operation: Operation, action: Callable[[AutomationSession], T]) -> T:
        self._session.mark_running(operation)
        result = action(self._session)
        logging.getLogger(self.__module__).info(
            "Operação concluída",
            extra=Operation.executed_operation(operation),
        )
        return result
