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


class ReassessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    diagnosis_id: int | None = Field(default=None, ge=1)
    new_diagnosis_id: int | None = Field(default=None, ge=1)
    reclassification_id: int | None = Field(default=None, ge=1)
    result_id: int | None = Field(default=None, ge=1)
    sample_revision: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)
    key: str | None = Field(default=None, min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=500)


class MarkPatternBadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    pattern_name: str | None = Field(default=None, min_length=3, max_length=30)
    name: str | None = Field(default=None, min_length=3, max_length=30)
    reason: str | None = Field(default=None, max_length=500)
    reassess: bool = False
    active: bool | None = None
    is_active: bool | None = None
    bad: bool | None = None
    is_bad: bool | None = None
    status: str | None = Field(default=None, max_length=30)
    state: str | None = Field(default=None, max_length=30)
