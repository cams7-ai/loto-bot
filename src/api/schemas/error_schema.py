from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[str] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": {
                        "code": "CONFIRMACAO_PAGAMENTO_DESABILITADA",
                        "message": "A confirmação de pagamento real está desabilitada.",
                    }
                }
            ]
        }
    )

    error: ErrorDetail
