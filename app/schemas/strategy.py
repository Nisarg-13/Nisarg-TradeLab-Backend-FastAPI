from pydantic import Field

from app.schemas.common import CamelModel


class CreateStrategyInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)


class UpdateStrategyInput(CamelModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = Field(None, alias="isActive")


class StrategyResponse(CamelModel):
    id: str
    name: str
    description: str | None
    is_active: bool = Field(alias="isActive")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CreateTagInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=50)


class UpdateTagInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=50)


class TagResponse(CamelModel):
    id: str
    name: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CreateMistakeInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)


class UpdateMistakeInput(CamelModel):
    name: str = Field(..., min_length=1, max_length=100)


class MistakeResponse(CamelModel):
    id: str
    name: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class SuccessResponse(CamelModel):
    success: bool
