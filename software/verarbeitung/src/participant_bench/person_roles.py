"""Exclude explicitly labelled instructors, preserving uncertain people and a local audit."""

import re
import unicodedata

from .ocr_layout import line_groups
from .schema import PageResult, Participant

VERSION = "participant-roles-v1"
UNCONFIRMED_ROLE = "Kursleiterrolle ohne eindeutigen eigenen Rollenbeleg; Person zur Prüfung erhalten"
INSTRUCTIONS = """Only attendees belong in the final participant data. Distinguish them from course staff.
For each extracted person report person_role and role_evidence. Explicit labels such as Kursleiter,
Kursleitung, Schulungsleiter, Seminarleiter, Trainer, Dozent, Referent, instructor or lecturer mean
person_role="instructor"; copy only that person's literal printed role label into role_evidence.
The application excludes these labelled instructors from participant export and evaluation.
A trainer name/signature in a page header or footer is course metadata, not an attendee row.
Never invent a person from a role label alone. Never classify a person as an instructor based on
their surname, organization, signature, first/last row position, or a role label elsewhere on the page.
For an unlabelled person row use person_role="participant" and role_evidence=null. If role assignment
is ambiguous use "unknown", keep the person and leave role_evidence=null. Preserve all other fields.
"""
LABEL = re.compile(r"(?<!\w)(?:kursleiter(?:in)?|kursleitung|schulungsleiter(?:in)?|schulungsleitung|"
                   r"seminarleiter(?:in)?|seminarleitung|trainer(?:in)?|dozent(?:in)?|referent(?:in)?|"
                   r"instructor|lecturer|facilitator|course\s+leader)(?!\w)", re.IGNORECASE)


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def contains(text: str, value: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(normalized(value)) + r"(?!\w)", normalized(text)))


def role_label(text: str, person: Participant) -> str | None:
    """Do not mistake a surname such as Trainer for a printed role label."""
    values = " ".join(field.value or "" for field in (
        person.first_name, person.last_name, person.personnel_number, person.department))
    for match in LABEL.finditer(text):
        label = match.group()
        if re.search(r"\b(?:kein|keine|nicht|not|no)\s*$", text[:match.start()], re.IGNORECASE):
            continue
        if len(list(LABEL.finditer(values))) < len(list(LABEL.finditer(text))) or not contains(values, label):
            return label
    return None


def person_in_context(person: Participant, text: str) -> bool:
    names = [field.value for field in (person.first_name, person.last_name) if field.value]
    return bool(names) and all(contains(text, name) for name in names)


def contexts(person: Participant, raw: dict, output_index: int) -> list[str]:
    data = raw.get("ocr", {})
    words = data.get("words", [])
    boxes = [field.bbox for field in (person.first_name, person.last_name, person.personnel_number) if field.bbox]
    box = person.bbox or (boxes[0] if boxes else None)
    result = []
    for group in line_groups(data):
        own_words = [words[i] for i in group if not box or
                     (words[i]["bbox"]["y0"] < box.y1 and words[i]["bbox"]["y1"] > box.y0)]
        if not own_words:
            continue
        text = " ".join(word["text"] for word in own_words)
        if not box and person.personnel_number.value and not contains(text, person.personnel_number.value):
            continue
        result.append(text)
    # A transcript without word/line positions cannot establish a person's row.
    for key in ("structure", "unlimited_ocr"):
        for row in raw.get(key, {}).get("row_evidence", []):
            if row["output_index"] == output_index:
                result.append(" ".join(cell["text"] for cell in row.get("source_cells", [])))
    return [text for text in result if person_in_context(person, text)]


def filter_page_people(page: PageResult, raw: dict) -> None:
    """Run before signature checks and final persistence; excluded people never enter roster matching."""
    if page.output_kind == "ocr_text" or not page.participants:
        return
    kept, excluded, index_map = [], [], []
    for index, person in enumerate(page.participants):
        evidence = None
        if page.method_id in ("vlm", "ocr_vlm"):
            if person.person_role == "instructor" and person.role_evidence:
                evidence = role_label(person.role_evidence, person)
        else:
            own_contexts = contexts(person, raw, index)
            # The marker and the person's observed name must belong to the same source row.
            evidence = next((label for text in own_contexts if (label := role_label(text, person))), None)
        if evidence:
            person.person_role, person.role_evidence = "instructor", evidence
            page.excluded_instructors.append(person)
            excluded.append(dict(source_output_index=index, role_label=evidence,
                                 reason="Explizite Kursleiter-/Trainerrolle; kein Teilnehmer"))
        else:
            if person.person_role == "instructor":
                person.person_role = "unknown"
                if UNCONFIRMED_ROLE not in person.review_notes:
                    person.review_notes.append(UNCONFIRMED_ROLE)
                if page.status == "success":
                    page.status = "partial"
            index_map.append(dict(source_output_index=index, output_index=len(kept)))
            kept.append(person)
    page.participants = kept
    previous = raw.get("person_role_filter", {}).get("excluded", [])
    raw["person_role_filter"] = dict(version=VERSION, excluded=previous + excluded, kept_participants=len(kept),
                                     output_index_mapping=index_map,
                                     excluded_instructors=len(page.excluded_instructors))
    if excluded:
        page.review_notes.append(f"{len(excluded)} ausdrücklich gekennzeichnete Kursleiter/Trainer ausgeschlossen")
