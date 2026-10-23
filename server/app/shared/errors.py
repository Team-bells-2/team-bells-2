from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Domain error raised by orchestrators; rendered as the PRD error shape."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Every error leaves the API as { "error": { "code", "message" } }."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content=_error_body(error.code, error.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        errors: Sequence[Mapping[str, Any]] = error.errors()
        first: Mapping[str, Any] = errors[0] if errors else {}
        location: Sequence[str | int] = first.get("loc", ())
        field = ".".join(str(part) for part in location if part != "body")
        message = f"{field}: {first.get('msg', 'invalid request')}" if field else "Invalid request."
        return JSONResponse(status_code=422, content=_error_body("validation_error", message))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content=_error_body("http_error", str(error.detail)))
