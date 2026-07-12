"""Execução padronizada de etapas dos casos de uso."""

from __future__ import annotations

import logging
from collections.abc import Callable

from domain import AutomationSession, Operation


class OperationExecutor:
    _session: AutomationSession

    def _execute(self, operation: Operation, action: Callable[[AutomationSession], object]) -> None:
        self._session.mark_running(operation)
        action(self._session)
        logging.getLogger(self.__module__).info(
            "Operação concluída",
            extra=Operation.executed_operation(operation),
        )
