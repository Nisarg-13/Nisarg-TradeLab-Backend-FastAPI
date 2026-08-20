from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def parse_allowed_origins(*sources: str | None) -> list[str]:
    origins: set[str] = set()

    for source in sources:
        if not source:
            continue

        for part in source.split(","):
            normalized = part.strip().rstrip("/")
            if normalized:
                origins.add(normalized)

    return list(origins)


def is_origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    if not origin:
        return True

    normalized_origin = origin.rstrip("/")
    return normalized_origin in allowed_origins


def configure_cors(app: FastAPI, allowed_origins: list[str]) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "PUT", "PATCH", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
