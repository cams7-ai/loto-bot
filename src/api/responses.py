"""Resposta JSON UTF-8."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from api.schemas import ErrorResponse, error_response_examples
from domain import ErrorCode


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


def error_response(
    description: str,
    *codes: ErrorCode,
    examples: dict[str, dict[str, Any]] | None = None,
) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            Utf8JSONResponse.media_type: {
                "examples": examples or error_response_examples(*codes),
            }
        },
    }
