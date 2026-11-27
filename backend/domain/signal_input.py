from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Purpose(StrEnum):
    DIAGNOSIS = "diagnosis"
    RETEST = "retest"


class SweepInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    harness_revision: int = Field(ge=1)
    meter_code: str = Field(min_length=3, max_length=30)
    purpose: Purpose


class LampReading(BaseModel):
    pattern_name: str = Field(min_length=3, max_length=30)
    first_mask: int = Field(ge=0, le=16383)
    second_mask: int = Field(ge=0, le=16383)
    settle_ms: int = Field(ge=0, le=2000)
    current_ma: int = Field(ge=0, le=2000)


class DiagnosisRequest(BaseModel):
    sample_revision: int = Field(ge=0)
