"""Resposta JSON UTF-8."""

from __future__ import annotations

from fastapi.responses import JSONResponse


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"
