from __future__ import annotations

from http import HTTPStatus

import pytest

from api.exceptions import ApiError
from api.mappers.api_exception_mapper import ApiExceptionMapper
from domain import (
    AutomationError,
    BetTemporarilyDisabledError,
    BrowserSessionClosedError,
    BrowserSessionOpenError,
    DailyPurchaseLimitError,
    ExternalServiceError,
    IndividualBetRegistrationClosedError,
    InvalidCPFError,
    InvalidPasswordError,
    PageRedirectionError,
    PaymentConfirmationDisabledError,
)


@pytest.mark.parametrize(
    ("exc", "expected_status_code"),
    [
        (AutomationError("Falha de automacao"), HTTPStatus.INTERNAL_SERVER_ERROR),
        (ExternalServiceError("Servico externo indisponivel"), HTTPStatus.SERVICE_UNAVAILABLE),
        (BrowserSessionOpenError(), HTTPStatus.CONFLICT),
        (BrowserSessionClosedError(), HTTPStatus.CONFLICT),
        (PageRedirectionError("/caminho"), HTTPStatus.BAD_GATEWAY),
        (InvalidCPFError(), HTTPStatus.BAD_REQUEST),
        (InvalidPasswordError(), HTTPStatus.BAD_REQUEST),
        (PaymentConfirmationDisabledError(), HTTPStatus.FORBIDDEN),
        (IndividualBetRegistrationClosedError(), HTTPStatus.CONFLICT),
        (BetTemporarilyDisabledError("Mega-Sena"), HTTPStatus.CONFLICT),
        (DailyPurchaseLimitError(), HTTPStatus.TOO_MANY_REQUESTS),
    ],
)
def test_api_exception_mapper_uses_status_code_from_domain_exception(
    exc: AutomationError,
    expected_status_code: HTTPStatus,
) -> None:
    with pytest.raises(ApiError) as raised:
        ApiExceptionMapper.raise_api_error(exc)

    assert exc.status_code == expected_status_code
    assert raised.value.status_code == expected_status_code.value
    assert raised.value.code == exc.code
    assert raised.value.message == str(exc)
