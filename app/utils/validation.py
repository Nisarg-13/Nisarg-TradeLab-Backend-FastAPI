from pydantic import BaseModel, ValidationError
from fastapi import HTTPException, status


def flatten_validation_error(error: ValidationError) -> dict[str, object]:
    field_errors: dict[str, list[str]] = {}
    form_errors: list[str] = []

    for item in error.errors():
        location = item.get("loc", ())
        message = item.get("msg", "Invalid value")

        if location == ("body",):
            form_errors.append(message)
            continue

        field = ".".join(str(part) for part in location if part != "body")
        if field:
            field_errors.setdefault(field, []).append(message)
        else:
            form_errors.append(message)

    return {"fieldErrors": field_errors, "formErrors": form_errors}


def parse_body(model: type[BaseModel], data: object) -> BaseModel:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=flatten_validation_error(exc),
        ) from exc
