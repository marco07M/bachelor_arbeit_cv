"""Strict shared data contracts. Coordinates are normalized on the oriented page."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TEXT_FIELDS = ("first_name", "last_name", "personnel_number", "department")
State = Literal["read", "empty", "illegible", "uncertain", "failed"]
Status = Literal["unavailable", "failed", "partial", "success"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Box(StrictModel):
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self):
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("Bounding box must have positive area")
        return self


class TextField(StrictModel):
    value: str | None = None
    state: State = "uncertain"
    bbox: Box | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.state == "read" and (self.value is None or not self.value.strip()):
            raise ValueError("read requires a nonempty string")
        if self.state == "empty" and self.value not in (None, ""):
            raise ValueError("empty cannot contain text")
        if self.state in ("illegible", "failed") and self.value is not None:
            raise ValueError("illegible/failed requires null")
        return self


class Participant(StrictModel):
    row_ref: str | None = None
    bbox: Box | None = None
    first_name: TextField
    last_name: TextField
    personnel_number: TextField
    department: TextField
    signature_present: bool | None = None
    signature_state: State = "uncertain"
    signature_bbox: Box | None = None
    review_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def signature_consistent(self):
        if self.signature_state == "empty" and self.signature_present is not False:
            raise ValueError("empty signature field requires false")
        if self.signature_present is None and self.signature_state in ("read", "empty"):
            raise ValueError("known signature state requires true/false")
        if self.signature_present is not None and self.signature_state not in ("read", "empty"):
            raise ValueError("unknown signature state requires null")
        return self


class ModelResponse(StrictModel):
    participants: list[Participant]


class PageResult(StrictModel):
    run_id: str
    document_id: str
    page_number: int = Field(ge=1)
    page_id: str
    method_id: str
    status: Status
    participants: list[Participant] = Field(default_factory=list)
    parse_status: Literal["valid", "invalid", "not_attempted"] = "not_attempted"
    error: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    calls: int = 0
    review_notes: list[str] = Field(default_factory=list)


class GroundTruthPage(StrictModel):
    document_id: str
    page_number: int = Field(ge=1)
    split: Literal["development", "test"]
    dependency_group: str
    content_type: Literal["typed", "handwritten", "mixed", "other"]
    relevant: bool
    participants: list[Participant]
