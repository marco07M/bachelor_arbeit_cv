"""Strict shared data contracts. Coordinates are normalized on the oriented page."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TEXT_FIELDS = ("first_name", "last_name", "personnel_number", "department")
State = Literal["read", "empty", "illegible", "uncertain", "failed"]
Status = Literal["unavailable", "failed", "partial", "success"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PersonRole(StrictModel):
    person_role: Literal["participant", "instructor", "unknown"] = Field(default="unknown", description=(
        "instructor only for a person explicitly labelled Kursleiter, Trainer, Dozent or equivalent. "
        "Never infer the role from a name, department, signature or row position."
    ))
    role_evidence: str | None = Field(default=None, max_length=120, description=(
        "Copy the literal role label belonging to this person, e.g. Kursleiter or Trainer. "
        "Use null when no explicit role label exists; never copy a label belonging to another person."
    ))


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


class Participant(PersonRole):
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


class VisualParticipant(PersonRole):
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
            person_role=self.person_role, role_evidence=self.role_evidence,
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


class NameOrderDecision(StrictModel):
    order: Literal["given_family", "family_given", "unknown"] = Field(description=(
        "Physical reading order of the two name parts in this document: given_family means first name "
        "before surname; family_given means surname before first name. Use unknown if not defensible."
    ))
    evidence: str = Field(description=(
        "Brief document evidence for the order: literal headings, their positions or a combined-name "
        "separator. Do not use an external roster, a name dictionary or guess from individual names."
    ))


class VisualPageResponse(StrictModel):
    name_order: NameOrderDecision | None = None
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


class VisualCellParticipant(PersonRole):
    """Read identity cells in physical column order before assigning semantic fields."""

    row_ref: str | None = None
    first_name: str | None
    last_name: str | None
    identity_cells: list[str | None] = Field(description=(
        "Exactly one cell per identity_headers column, in the same left-to-right order. "
        "Include name and row-number cells too. Keep empty cells as ''. "
        "Use null for masked, illegible, date or signature cells. Never shift cells."
    ))
    signature_present: bool | None = None


class VisualCellPageResponse(StrictModel):
    name_order: NameOrderDecision | None = None
    identity_headers: list[str | None] = Field(description=(
        "ALL literal printed table headings in physical left-to-right order, including row number, "
        "names, user ID, department, date and signature columns if present. Include empty columns. "
        "A page may have no user-ID column at all; never add a missing column or invent a heading. "
        "Use null for an unreadable heading; never infer column roles from the cell values."
    ))
    participants: list[VisualCellParticipant]
    page_text: str | None

    @model_validator(mode="after")
    def fallback_text(self):
        if self.participants:
            self.page_text = None
        elif self.page_text is None:
            raise ValueError("No participants: provide the visible page text as fallback, or '' for a blank page")
        return self


class OCRParticipant(PersonRole):
    is_participant: bool = Field(default=True, description=(
        "True only for an actual person entry. False for titles, course metadata, instructions, headers "
        "or footers. Never turn the first word and the remaining sentence into a person's names."
    ))
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
    name_order: NameOrderDecision | None = None
    participants: list[OCRParticipant]


class OCRTextRow(PersonRole):
    source_row: str
    is_participant: bool = True
    first_name: str | None
    last_name: str | None
    personnel_number: str | None
    department: str | None


class OCRTextPageResponse(StrictModel):
    name_order: NameOrderDecision | None = None
    participants: list[OCRTextRow]


class OCRRecordResponse(StrictModel):
    participants: list[OCRTextRow]


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
    excluded_instructors: list[Participant] = Field(default_factory=list)
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
