"""Client HTTP local ou AWS Lambda para leitura do código de validação."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from application import ValidationCodePort
from domain import (
    ErrorMessage,
    ExternalServiceError,
    Operation,
)
from infrastructure.config import Settings
from shared import mask_sensitive_value

logger = logging.getLogger(__name__)


class GmailReaderClient(ValidationCodePort):
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    def _lambda_client(self) -> Any:
        if self._client is None:
            self._client = __import__("boto3").client("lambda")
        return self._client

    def _http_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._settings.validation_code_wait_timeout_seconds + 5)
        return self._client

    def get_validation_code(self, operation: Operation) -> str:
        logger.info(
            "Chamando API Gmail Reader para buscar código de validação",
            extra=Operation.executed_operation(operation),
        )
        payload = self._get_payload(operation)
        code = str(payload.get("code", "")).strip()
        if not code:
            raise ExternalServiceError(ErrorMessage.GMAIL_READER_API_VALIDATION_CODE_NOT_RETURNED, operation=operation)

        mask_sensitive_value(code)
        return code

    def _get_payload(self, operation: Operation) -> dict[str, Any]:
        try:
            if self._settings.integration_mode == "LOCAL":
                response = self._http_client().get(
                    f"{self._settings.gmail_reader_url}/api/v1/validation-code",
                    params={"waitTimeoutSeconds": self._settings.validation_code_wait_timeout_seconds},
                    timeout=self._settings.validation_code_wait_timeout_seconds + 5,
                )
                if response.status_code >= 400:
                    raise ExternalServiceError(ErrorMessage.VALIDATION_CODE_FETCH_FAILED, operation=operation)
                return response.json()

            response = self._lambda_client().invoke(
                FunctionName=self._settings.gmail_reader_function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps({"waitTimeoutSeconds": self._settings.validation_code_wait_timeout_seconds}).encode(
                    "utf-8"
                ),
            )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ExternalServiceError(ErrorMessage.VALIDATION_CODE_FETCH_TIMEOUT, operation=operation) from exc

        lambda_payload = json.loads(response["Payload"].read())
        if response.get("FunctionError") or lambda_payload.get("statusCode", 500) >= 400:
            raise ExternalServiceError(ErrorMessage.VALIDATION_CODE_FETCH_FAILED, operation=operation)
        return json.loads(lambda_payload["body"])
