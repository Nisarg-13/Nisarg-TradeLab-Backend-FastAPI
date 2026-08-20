from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        ser_json_by_alias=True,
    )


class DataEnvelope(BaseModel, Generic[T]):
    data: T
