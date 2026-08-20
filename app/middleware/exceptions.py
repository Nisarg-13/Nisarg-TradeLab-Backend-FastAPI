import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

HTTP_STATUS_NAMES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "UNPROCESSABLE_ENTITY",
    status.HTTP_429_TOO_MANY_REQUESTS: "TOO_MANY_REQUESTS",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
}


def _status_code_name(status_code: int) -> str:
    return HTTP_STATUS_NAMES.get(status_code, "HTTP_ERROR")


def normalize_payload(payload: Any, status_code: int) -> dict[str, Any]:
    if isinstance(payload, dict) and "error" in payload:
        return payload

    if isinstance(payload, str):
        return {
            "error": {
                "code": _status_code_name(status_code),
                "message": payload,
            }
        }

    if isinstance(payload, dict) and ("fieldErrors" in payload or "formErrors" in payload):
        field_errors = payload.get("fieldErrors") or {}
        form_errors = payload.get("formErrors") or []
        field_messages = [
            f"{field}: {message}"
            for field, messages in field_errors.items()
            for message in messages
        ]
        return {
            "error": {
                "code": _status_code_name(status_code),
                "message": "; ".join([*form_errors, *field_messages]) or "Request failed.",
                "details": payload,
            }
        }

    if isinstance(payload, dict) and "message" in payload:
        message = payload["message"]
        return {
            "error": {
                "code": _status_code_name(status_code),
                "message": ", ".join(message) if isinstance(message, list) else str(message),
                "details": payload.get("details"),
            }
        }

    return {
        "error": {
            "code": _status_code_name(status_code),
            "message": "Request failed.",
        }
    }


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    payload = exc.detail
    if isinstance(payload, dict) and "error" in payload:
        body = payload
    else:
        body = normalize_payload(payload, exc.status_code)
    return JSONResponse(status_code=exc.status_code, content=body)


async def starlette_http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    body = normalize_payload(exc.detail, exc.status_code)
    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors: dict[str, list[str]] = {}
    form_errors: list[str] = []

    for error in exc.errors():
        if error.get("type") == "json_invalid":
            form_errors.append(error.get("msg", "Invalid JSON"))
            continue

        location = error.get("loc", ())
        if len(location) >= 2 and location[0] == "body":
            field = ".".join(str(part) for part in location[1:])
            field_errors.setdefault(field, []).append(error.get("msg", "Invalid value"))
        else:
            form_errors.append(error.get("msg", "Invalid value"))

    body = normalize_payload(
        {"fieldErrors": field_errors, "formErrors": form_errors},
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    settings: Settings = get_settings()
    logger.error(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )

    message = (
        "An unexpected error occurred."
        if settings.is_production
        else exc.__class__.__name__ + ": " + str(exc)
        if str(exc)
        else "An unexpected error occurred."
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
