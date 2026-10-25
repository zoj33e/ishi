"""API error shape `{"error": {"code", "message_key", "details"}}` (see 08-api-spec)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ishi.engine.katago_process import EngineUnavailableError


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message_key: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message_key = message_key
        self.details = details or {}


def _body(code: str, message_key: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"error": {"code": code, "message_key": message_key, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message_key, exc.details), status_code=exc.status)

    @app.exception_handler(EngineUnavailableError)
    async def _engine_down(_: Request, exc: EngineUnavailableError) -> JSONResponse:
        return JSONResponse(_body("ENGINE_OFFLINE", "errors.engine_offline", {}), status_code=503)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        body = _body("INVALID_REQUEST", "errors.invalid_request", {"errors": errors})
        return JSONResponse(body, status_code=422)
