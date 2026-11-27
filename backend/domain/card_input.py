from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Mode(StrEnum):
    RESEAT = "reseat"
    SWAP = "swap"


class CardInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    diagnosis_id: int = Field(ge=1)
    mode: Mode
    spare_serial: str | None = Field(default=None, min_length=3, max_length=30)


class FitInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    installation_note: str = Field(min_length=12, max_length=500)


class ReleaseInput(BaseModel):
    retest_id: int = Field(ge=1)
    sample_revision: int = Field(ge=1)
