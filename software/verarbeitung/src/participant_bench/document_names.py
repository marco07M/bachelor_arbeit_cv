"""One model-decided name convention per document, applied to observed name positions only."""

import json
import re
import time
import unicodedata

from .io import read_json, write_json
from .ocr_evidence import observed_spans
from .schema import NameOrderDecision, PageResult, Participant

VERSION = "document-name-order-v2-safe-context"
REVIEW = "Namensreihenfolge im Dokument nicht eindeutig belegt; Vor-/Nachname manuell prüfen"
INSTRUCTIONS = """Decide the NAME ORDER ONCE FOR THE DOCUMENT, not separately for each person.
Return name_order with order=given_family, family_given or unknown and a brief evidence string.
Evidence must be at most 30 words. Quote only relevant headings, never repeat source text or people's names.
The top-level JSON MUST start with the required name_order object, before participants. Example
shape only: {"name_order":{"order":"family_given","evidence":"Nachname, Vorname"},"participants":[...]}
given_family means the physical name text reads GIVEN NAME then FAMILY NAME; family_given means
FAMILY NAME then GIVEN NAME. Use literal headings (Vorname/First Name versus Nachname/Last Name),
column positions, and combined-name separators such as 'Nachname, Vorname'. A combined Benutzername
column is a NAME column; it is not a user ID. Read each whole name part, including compound names.
The input may contain DOCUMENT_NAME_ORDER_CONTEXT from an earlier page of this SAME PDF. Follow
that document convention on continuation pages; do not reconsider the order from each person's name.
If the current printed headings contradict that context, report your observed order so the application
can flag the conflict. If evidence is insufficient, report unknown instead of guessing.
Never use an external participant roster or guess by nationality, common first names or a dictionary.
Keep original spelling and never invent, complete or replace name parts. Return first_name and
last_name as usual, and for VLM keep the literal name cells in their physical identity_cells positions.
"""


def infer_text_order(model, rows, hint=None):
    """A short decision by the already-loaded text LLM; never image-based recognition."""
    system = ("Determine physical name-part order from supplied OCR text only. Return ONLY the JSON "
              "object with order (given_family, family_given or unknown) and evidence (at most 20 words). "
              "Do not return participants, names, cells or copy the source. Prefer headings and separators; "
              "use unknown if the order cannot be established. This is one decision for this document.")
    text = json.dumps(dict(name_column_hint=hint, examples=[dict(source_row=row["id"], cells=row.get("column_texts", []))
                                                          for row in rows[:4]]), ensure_ascii=False)
    record = dict(text_prompt=text, system_prompt=system, model_call=True)
    model.calls += 1
    try:
        answer, metadata = model.generate(text, max_new_tokens=192, response_type=NameOrderDecision, system_prompt=system)
        record.update(raw_response=answer, metadata=metadata)
        if metadata.get("output_budget_reached"):
            raise ValueError("Name-order decision reached output budget")
        decision = NameOrderDecision.model_validate_json(answer)
        record["parse_status"] = "valid"
    except Exception as exc:
        record.update(parse_status="invalid", error_type=type(exc).__name__)
        decision = NameOrderDecision(order="unknown", evidence="Textuelle Namensreihenfolge nicht eindeutig; manuell prüfen")
    return decision, record


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def spans(text: str, value: str):
    return list(re.finditer(r"(?<![\w’'-])" + re.escape(normalized(value)) + r"(?![\w’'-])", normalized(text)))


def cell_positions(cells, first: str, last: str):
    positions = []
    for value in (first, last):
        matches = [(index, match.start()) for index, cell in enumerate(cells) if isinstance(cell, str)
                   for match in spans(cell, value)]
        if len(matches) != 1:
            return None
        positions.append(matches[0])
    return tuple(positions) if positions[0] != positions[1] else None


def name_positions(person: Participant, raw: dict, output_index: int):
    first, last = person.first_name.value, person.last_name.value
    if not first or not last or normalized(first) == normalized(last):
        return None
    a, b = person.first_name.bbox, person.last_name.bbox
    if a and b and abs(a.x0 - b.x0) > 0.002:
        return ((a.x0, 0), (b.x0, 0))
    words = raw.get("ocr", {}).get("words", [])
    if words:
        found = []
        for value in (first, last):
            options = observed_spans(words, value)
            if person.bbox:
                options = [indices for indices in options if all(
                    words[i]["bbox"]["y0"] < person.bbox.y1 and words[i]["bbox"]["y1"] > person.bbox.y0
                    for i in indices)]
            if len(options) != 1:
                break
            found.append((min(words[i]["bbox"]["x0"] for i in options[0]), 0))
        if len(found) == 2 and found[0] != found[1]:
            return tuple(found)
    candidates = []
    for response in raw.get("responses", []):
        try:
            payload = json.loads(response.get("raw_response", "{}"))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        for row in payload.get("participants", []):
            if not isinstance(row, dict) or "identity_cells" not in row:
                continue
            if person.row_ref and row.get("row_ref") != person.row_ref:
                continue
            position = cell_positions(row["identity_cells"], first, last)
            if position:
                candidates.append(position)
    for key in ("structure", "unlimited_ocr"):
        for proof in raw.get(key, {}).get("row_evidence", []):
            if proof["output_index"] == output_index:
                position = cell_positions([cell["text"] for cell in proof.get("source_cells", [])], first, last)
                if position:
                    candidates.append(position)
    return candidates[0] if candidates and len(set(candidates)) == 1 else None


class DocumentNameOrders:
    def __init__(self):
        self.decisions: dict[str, NameOrderDecision] = {}
        self.origins: dict[str, int] = {}
        self.conflicts: set[str] = set()

    def context(self, document_id: str):
        decision = self.decisions.get(document_id)
        return dict(order=decision.order, evidence=f"Dokumentreihenfolge auf Seite {self.origins.get(document_id, 1)} festgelegt; keine früheren Personenwerte übernehmen") if decision else None

    def restore(self, page: PageResult, raw: dict):
        audit = raw.get("document_name_order", {})
        if audit.get("version") == VERSION and audit.get("decision"):
            decision = NameOrderDecision.model_validate(audit["decision"])
            if decision.order != "unknown":
                self.decisions[page.document_id] = decision
                self.origins[page.document_id] = audit.get("origin_page", page.page_number)
        if audit.get("conflicting_page_decision"):
            self.conflicts.add(page.document_id)

    def choose(self, document_id, page_number, decisions):
        proposed = next((item for item in decisions if item.order != "unknown" and item.evidence.strip()), None)
        previous = self.decisions.get(document_id)
        if (previous and proposed and proposed.order != previous.order) or len(
                {item.order for item in decisions if item.order != "unknown"}) > 1:
            self.conflicts.add(document_id)
        selected = previous or proposed
        if selected and document_id not in self.conflicts:
            self.decisions[document_id] = selected
            self.origins.setdefault(document_id, page_number)
        return selected, document_id in self.conflicts

    def prepare_assignment(self, response, rows, document_id, page_number):
        selected, conflict = self.choose(document_id, page_number, [response.name_order] if response.name_order else [])
        if not selected or conflict:
            return []
        by_id, changes = {row["id"]: row for row in rows}, []
        for index, person in enumerate(response.participants):
            row = by_id.get(person.source_row)
            first, last = person.first_name[1], person.last_name[1]
            if not row or not first or not last:
                continue
            position = cell_positions([cell["text"] for cell in row["cells"]], first, last)
            if position and ("given_family" if position[0] < position[1] else "family_given") != selected.order:
                person.first_name, person.last_name = person.last_name, person.first_name
                changes.append(dict(source_output_index=index, source_row=person.source_row, action="swap_before_cell_validation"))
        return changes

    def apply(self, page: PageResult, raw: dict, decision: NameOrderDecision | None = None):
        decisions = [decision] if decision else [NameOrderDecision.model_validate(response["name_order"])
            for response in raw.get("responses", []) if response.get("name_order") is not None]
        if not decisions and page.document_id not in self.decisions:
            return  # Historical responses without this contract keep their original semantics.
        selected, conflict = self.choose(page.document_id, page.page_number, decisions)
        previous_actions = {row["source_output_index"]: row for row in raw.get("document_name_order", {}).get("actions", [])}
        source_indices = {row["output_index"]: row["source_output_index"]
                          for row in raw.get("person_role_filter", {}).get("output_index_mapping", [])}
        actions = []
        for index, person in enumerate(page.participants):
            source_index = source_indices.get(index, index)
            previous = previous_actions.get(source_index, {})
            proof_rows = [proof for key in ("structure", "unlimited_ocr") for proof in raw.get(key, {}).get("row_evidence", [])
                          if proof["output_index"] == source_index]
            prevalidation_swap = any(change.get("source_row") == proof.get("source_row")
                for change in raw.get("assignment", {}).get("name_changes_before_validation", []) for proof in proof_rows)
            states = previous.get("original_states", dict(first_name=person.first_name.state, last_name=person.last_name.state))
            if previous.get("action") == "review":
                for field, state in states.items():
                    getattr(person, field).state = state
            position = name_positions(person, raw, source_index)
            if not conflict and selected and position:
                observed = "given_family" if position[0] < position[1] else "family_given"
                swap = observed != selected.order
                if swap:
                    person.first_name, person.last_name = person.last_name, person.first_name
                    person.review_notes.append("Vor-/Nachnamenfelder nach dokumentweiter Modellentscheidung vertauscht; Originalwerte in Rohantwort")
                actions.append(dict(source_output_index=source_index, action="swap" if swap else "keep",
                                    original_states=states, prevalidation_swap=prevalidation_swap,
                                    previously_swapped=previous.get("action") == "swap" or previous.get("previously_swapped", False)))
                if REVIEW in person.review_notes:
                    person.review_notes.remove(REVIEW)
            else:
                # Preserve the actual text for manual review; never borrow values from Excel or another row.
                if REVIEW not in person.review_notes:
                    person.review_notes.append(REVIEW)
                for field in (person.first_name, person.last_name):
                    if field.value:
                        field.state = "uncertain"
                actions.append(dict(source_output_index=source_index, action="review", original_states=states))
        if any(item["action"] == "review" for item in actions):
            if REVIEW not in page.review_notes:
                page.review_notes.append(REVIEW)
            if page.status == "success":
                page.status = "partial"
        elif REVIEW in page.review_notes:
            page.review_notes.remove(REVIEW)
        raw["document_name_order"] = dict(version=VERSION, decision=selected.model_dump() if selected else None,
            reported_decisions=[item.model_dump() for item in decisions],
            origin_page=self.origins.get(page.document_id), scope="document", conflicting_page_decision=conflict,
            actions=actions)

    def finalize(self, pages, method_dir):
        """Revisit earlier pages when a later heading established the convention; no new inference."""
        for page in pages:
            path = method_dir / f"raw-{page.page_id}.json"
            if not path.is_file() or page.document_id not in self.decisions:
                continue
            started = time.perf_counter()
            raw = read_json(path)
            assignment_decision = raw.get("assignment", {}).get("name_order")
            self.apply(page, raw, NameOrderDecision.model_validate(assignment_decision) if assignment_decision else None)
            elapsed = time.perf_counter() - started
            page.timings["name_order_reconciliation_seconds"] = elapsed
            page.timings["page_wall_seconds"] = page.timings.get("page_wall_seconds", 0) + elapsed
            page.timings["page_overhead_seconds"] = page.timings.get("page_overhead_seconds", 0) + elapsed
            raw["status"] = page.status
            write_json(path, raw)
