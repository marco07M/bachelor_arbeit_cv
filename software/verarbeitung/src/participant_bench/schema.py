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
    signature_method: str | None = None
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


class VisualParticipant(StrictModel):
    """Compact VLM output; empty strings and unknown nulls remain distinguishable."""

    row_ref: str | None = None
    first_name: str | None
    last_name: str | None
    personnel_number: str | None = Field(description=(
        "Value only from this person's Benutzer / User ID / Personalnummer cell. "
        "Use '' if visibly blank, null if masked, unreadable or ambiguous. "
        "Never substitute Kurzzeichen, department or a course/Class ID. Keep the person even without this ID."
    ))
    department: str | None = Field(description=(
        "Value only from Kurzzeichen / Abteilung / Organisation in this person's row, even when Benutzer is blank. "
        "May contain letters, digits, hyphens or slashes. Use '' if visibly blank, null if unknown."
    ))
    signature_present: bool | None = None

    def participant(self) -> Participant:
        fields = {}
        for name in TEXT_FIELDS:
            value = getattr(self, name)
            if isinstance(value, str) and not value.strip():
                value = ""
            state = "uncertain" if value is None else "empty" if not value.strip() else "read"
            fields[name] = TextField(value=value, state=state)
        return Participant(
            row_ref=self.row_ref,
            **fields,
            signature_present=self.signature_present,
            signature_state=(
                "uncertain" if self.signature_present is None
                else "read" if self.signature_present else "empty"
            ),
        )


class SignatureResponse(StrictModel):
    field_located: bool
    signature_present: bool | None
    evidence: Literal["handwritten_mark", "blank_field", "unclear", "no_field", "printed_text"]

    @model_validator(mode="after")
    def consistent(self):
        if self.signature_present is not None and not self.field_located:
            raise ValueError("A signature decision requires a localized signature field")
        if self.signature_present is True and self.evidence != "handwritten_mark":
            raise ValueError("Positive signature presence requires handwritten mark evidence")
        if self.signature_present is False and self.evidence != "blank_field":
            raise ValueError("Negative signature presence requires a visibly blank field")
        if self.signature_present is None and self.evidence in ("handwritten_mark", "blank_field"):
            raise ValueError("Definite evidence requires a presence decision")
        return self


class SignatureRowLocation(StrictModel):
    output_index: int = Field(ge=0)
    row_y: tuple[int | None, int | None] | None = Field(
        description="Top and bottom on a 0..1000 coordinate scale; null if unlocatable."
    )


class SignatureLocations(StrictModel):
    rows: list[SignatureRowLocation]


class VisualPageResponse(StrictModel):
    participants: list[VisualParticipant]
    page_text: str | None = Field(
        description="Fallback only: transcribe all legible text if participants is empty; otherwise null."
    )

    @model_validator(mode="after")
    def fallback_text(self):
        if self.participants:
            self.page_text = None
        elif self.page_text is None:
            raise ValueError("No participants: provide the visible page text as fallback, or '' for a blank page")
        return self


class OCRParticipant(StrictModel):
    ocr_line_id: int | None = Field(default=None, ge=1, description="line_id from OCR_LAYOUT_DATA.lines for this person row")
    row_ref: str | None = None
    first_name: str | None
    last_name: str | None
    personnel_number: str | None
    department: str | None
    word_ids: list[int] = Field(
        default_factory=list,
        description="IDs of the observed OCR words in this participant row; no invented word IDs.",
    )


class OCRPageResponse(StrictModel):
    participants: list[OCRParticipant]


class PageResult(StrictModel):
    run_id: str
    document_id: str
    page_number: int = Field(ge=1)
    page_id: str
    method_id: str
    status: Status
    output_kind: Literal["structured", "ocr_text"] = "structured"
    page_text: str | None = None
    text_fallback: bool = False
    participants: list[Participant] = Field(default_factory=list)
    parse_status: Literal["valid", "invalid", "not_attempted"] = "not_attempted"
    error: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    calls: int = 0
    review_notes: list[str] = Field(default_factory=list)


class GroundTruthPage(StrictModel):
    document_id: str
    page_number: int = Field(ge=1)
    split: Literal["development", "validation", "test"]
    dependency_group: str
    content_type: Literal["typed", "handwritten", "mixed", "other"]
    relevant: bool
    participants: list[Participant]
