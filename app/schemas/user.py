from pydantic import Field, field_validator

from app.schemas.common import CamelModel


class UpdateUserInput(CamelModel):
    timezone: str | None = Field(None, min_length=1)
    preferred_currency: str | None = Field(None, min_length=3, max_length=3, alias="preferredCurrency")
    selected_trading_account_id: str | None = Field(
        None, min_length=1, alias="selectedTradingAccountId"
    )

    @field_validator("selected_trading_account_id", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class UserFeaturesResponse(CamelModel):
    ai_coach: bool = Field(alias="aiCoach")


class UserResponse(CamelModel):
    id: str
    email: str
    timezone: str
    preferred_currency: str = Field(alias="preferredCurrency")
    selected_trading_account_id: str | None = Field(alias="selectedTradingAccountId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    features: UserFeaturesResponse
