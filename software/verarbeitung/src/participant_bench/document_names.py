"""One model-decided name convention per document, applied to observed name positions only."""

import json
import re
import time
import unicodedata

from .io import read_json, write_json
from .name_parts import DEFAULT_ORDER, matching_comma_cells, matching_name_cells, split_combined_name
from .ocr_evidence import observed_spans
from .schema import NameOrderDecision, PageResult, Participant

VERSION = "document-name-order-v3-family-first-default"
REVIEW = "Namensreihenfolge im Dokument nicht eindeutig belegt; Vor-/Nachname manuell prüfen"
INSTRUCTIONS = """Decide the NAME ORDER ONCE FOR THE DOCUMENT, not separately for each person.
Return name_order with order=given_family, family_given or unknown, basis=document/default/unknown,
and a brief evidence string. Use basis=document only for visible headings/separators, basis=default
for the user's surname-first convention without such evidence.
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
can flag the conflict. If no clear headings or separators establish another order, use the user's
DEFAULT family_given: the FIRST WHOLE NAME GROUP is the surname, the following group contains ALL
given names, including second and third given names. Label this as a default assumption in evidence.
For 'Surname, Given names', EVERYTHING before the comma is last_name and EVERYTHING after it is
first_name. Preserve multiword and hyphenated surnames as ONE whole group; never move the second
surname component into first_name. Separate printed first/last-name columns take precedence over
the default. Without a separator or layout evidence, a multiword surname versus extra given names
can be ambiguous: preserve supported complete groups and use null for a split you cannot establish.
Never use an external participant roster or guess by nationality, common first names or a dictionary.
Keep original spelling and never invent, complete or replace name parts. Return first_name and
last_name as usual, and for VLM keep the literal name cells in their physical identity_cells positions.
"""


def infer_text_order(model, rows, hint=None):
    """A short decision by the already-loaded text LLM; never image-based recognition."""
    system = ("Determine physical name-part order from supplied OCR text only. Return ONLY the JSON "
              "object with order (given_family, family_given or unknown), basis (document/default/unknown) "
              "and evidence (at most 20 words). "
              "Do not return participants, names, cells or copy the source. Prefer headings and separators; "
              "Without explicit evidence use family_given with basis=default, the user's surname-first default. "
              "Keep compound surname groups and all given names together. This is one decision for this document.")
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


def observed_name_cells(person, raw, source_index):
    cells = []
    for change in raw.get("assignment", {}).get("name_changes_before_validation", []):
        if change.get("source_output_index") == source_index and change.get("name_cell_text"):
            cells.append(dict(text=change["name_cell_text"]))
    for key in ("structure", "unlimited_ocr"):
        for proof in raw.get(key, {}).get("row_evidence", []):
            if proof["output_index"] == source_index:
                cells.extend(proof.get("source_cells", []))
    for response in raw.get("responses", []):
        try:
            payload = json.loads(response.get("raw_response", "{}"))
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        for row in payload.get("participants", []):
            if isinstance(row, dict) and (not person.row_ref or row.get("row_ref") == person.row_ref):
                cells.extend(dict(text=c) for c in row.get("identity_cells", []) if isinstance(c, str))
    for row in raw.get("ocr", {}).get("text_rows", []):
        cells.extend(row.get("cells", []))
    return cells


class DocumentNameOrders:
    def __init__(self, default_order=DEFAULT_ORDER):
        self.decisions: dict[str, NameOrderDecision] = {}
        self.origins: dict[str, int] = {}
        self.conflicts: set[str] = set()
        self.default_order = default_order
        self.sources: dict[str, str] = {}

    def context(self, document_id: str):
        decision = self.decisions.get(document_id)
        return dict(order=decision.order, basis=decision.basis, evidence=f"Dokumentreihenfolge auf Seite {self.origins.get(document_id, 1)} festgelegt; keine früheren Personenwerte übernehmen") if decision else None

    def restore(self, page: PageResult, raw: dict):
        audit = raw.get("document_name_order", {})
        if audit.get("version") == VERSION and audit.get("decision"):
            decision = NameOrderDecision.model_validate(audit["decision"])
            if decision.order != "unknown":
                self.decisions[page.document_id] = decision
                self.origins[page.document_id] = audit.get("origin_page", page.page_number)
                self.sources[page.document_id] = audit.get("decision_source", "model")
        if audit.get("conflicting_page_decision"):
            self.conflicts.add(page.document_id)

    def choose(self, document_id, page_number, decisions):
        explicit = [item for item in decisions if item.order != "unknown" and item.evidence.strip()
                    and item.basis == "document"]
        proposed = next(iter(explicit), None)
        previous = self.decisions.get(document_id)
        if proposed and self.sources.get(document_id) == "user_default":
            previous = None  # Later explicit headings can replace an assumption without a false conflict.
        if (previous and proposed and proposed.order != previous.order) or len(
                {item.order for item in explicit}) > 1:
            self.conflicts.add(document_id)
        selected = previous or proposed
        source = self.sources.get(document_id, "model") if previous else "model"
        if not selected and decisions and self.default_order != "unknown":
            selected = NameOrderDecision(order=self.default_order, basis="default",
                evidence="Vorgegebene Standardreihenfolge: Nachname zuerst, danach sämtliche Vornamen")
            source = "user_default"
        if selected and document_id not in self.conflicts:
            self.decisions[document_id] = selected
            if self.sources.get(document_id) == "user_default" and source == "model":
                self.origins[document_id] = page_number
            self.origins.setdefault(document_id, page_number)
            self.sources[document_id] = source
        return selected, document_id in self.conflicts

    def prepare_assignment(self, response, rows, document_id, page_number):
        selected, conflict = self.choose(document_id, page_number, [response.name_order] if response.name_order else [])
        if not selected or conflict:
            return []
        from .structure_assignment import header_bands

        bands = header_bands(rows)
        by_id, changes = {row["id"]: row for row in rows}, []
        for index, person in enumerate(response.participants):
            row = by_id.get(person.source_row)
            first, last = person.first_name[1], person.last_name[1]
            if not row or not first or not last:
                continue
            cells = list(row.get("native_cells") or row["cells"])
            band = bands.get("first_name")
            if band and band == bands.get("last_name") and row.get("native_cells"):
                text = " ".join(c["text"] for c in row["native_cells"] if band[0] <= c["bbox"]["x0"] < band[1])
                cells.append(dict(text=text))
            candidates = matching_comma_cells(cells, first, last)
            candidates = list({cell["text"]: cell for cell in candidates}.values())
            if len(candidates) == 1:
                cell = candidates[0]
                parents = [c for c in row["cells"] if cell["text"] in c["text"]]
                if len(parents) != 1:
                    continue
                given, family, _ = split_combined_name(cell["text"])
                if (first, last) != (given, family):
                    person.first_name, person.last_name = (parents[0]["index"], given), (parents[0]["index"], family)
                    changes.append(dict(source_output_index=index, source_row=person.source_row,
                                        action="split_combined_name_before_validation", name_cell_text=cell["text"]))
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
                and change.get("action") == "swap_before_cell_validation"
                for change in raw.get("assignment", {}).get("name_changes_before_validation", []) for proof in proof_rows)
            prevalidation_split = any(change.get("source_row") == proof.get("source_row")
                and change.get("action") == "split_combined_name_before_validation"
                for change in raw.get("assignment", {}).get("name_changes_before_validation", []) for proof in proof_rows)
            states = previous.get("original_states", dict(first_name=person.first_name.state, last_name=person.last_name.state))
            if previous.get("action") == "review":
                for field, state in states.items():
                    getattr(person, field).state = state
            position = name_positions(person, raw, source_index)
            cells = observed_name_cells(person, raw, source_index)
            comma_cells = matching_comma_cells(cells, person.first_name.value, person.last_name.value)
            comma_values = {c["text"] for c in comma_cells}
            if not conflict and len(comma_values) == 1:
                given, family, _ = split_combined_name(next(iter(comma_values)))
                original = person.first_name.value, person.last_name.value
                action = "keep" if original == (given, family) else "swap" if original == (family, given) else "split"
                if action == "swap":
                    person.first_name, person.last_name = person.last_name, person.first_name
                elif action == "split" and any(f.state == "uncertain" for f in (person.first_name, person.last_name)):
                    person.first_name.state = person.last_name.state = "uncertain"
                # The full combined source cell supports both parts; do not retain boxes of wrongly cut fragments.
                a, b = person.first_name.bbox, person.last_name.bbox
                box = type(a)(x0=min(a.x0,b.x0), y0=min(a.y0,b.y0), x1=max(a.x1,b.x1), y1=max(a.y1,b.y1)) if a and b else None
                person.first_name.value, person.last_name.value = given, family
                person.first_name.bbox = person.last_name.bbox = box
                actions.append(dict(source_output_index=source_index, action=action, original_states=states,
                                    assignment_rule="explicit_surname_comma_given_name",
                                    prevalidation_swap=prevalidation_swap,
                                    prevalidation_split=prevalidation_split,
                                    previously_swapped=previous.get("action") == "swap" or previous.get("previously_swapped", False),
                                    previously_split=previous.get("action") == "split" or previous.get("previously_split", False)))
                if REVIEW in person.review_notes:
                    person.review_notes.remove(REVIEW)
            elif not conflict and selected and position:
                observed = "given_family" if position[0] < position[1] else "family_given"
                swap = observed != selected.order
                if swap:
                    person.first_name, person.last_name = person.last_name, person.first_name
                    person.review_notes.append("Vor-/Nachnamenfelder nach dokumentweiter Modellentscheidung vertauscht; Originalwerte in Rohantwort")
                ambiguous_groups = self.sources.get(page.document_id) == "user_default" and any(
                    "," not in c["text"] and len(c["text"].split()) > 2
                    for c in matching_name_cells(cells, person.first_name.value, person.last_name.value))
                if ambiguous_groups:
                    if REVIEW not in person.review_notes:
                        person.review_notes.append(REVIEW)
                    person.first_name.state = person.last_name.state = "uncertain"
                actions.append(dict(source_output_index=source_index, action="review" if ambiguous_groups else "swap" if swap else "keep",
                                    group_split_uncertain=ambiguous_groups,
                                    original_states=states, prevalidation_swap=prevalidation_swap,
                                    prevalidation_split=prevalidation_split,
                                    previously_swapped=previous.get("action") == "swap" or previous.get("previously_swapped", False)))
                if not ambiguous_groups and REVIEW in person.review_notes:
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
            decision_source=self.sources.get(page.document_id), default_order=self.default_order,
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
