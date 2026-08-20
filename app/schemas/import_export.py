from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CsvFormat = Literal["AUTO", "MT5", "GENERIC"]


class CsvImportPreviewInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    csv: str = Field(min_length=1, max_length=5_000_000)
    trading_account_id: str = Field(min_length=1, alias="tradingAccountId")
    format: CsvFormat = "AUTO"


class CsvImportCommitInput(CsvImportPreviewInput):
    skip_duplicates: bool = Field(default=True, alias="skipDuplicates")


class ExportQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    trading_account_id: str | None = Field(default=None, min_length=1, alias="tradingAccountId")
