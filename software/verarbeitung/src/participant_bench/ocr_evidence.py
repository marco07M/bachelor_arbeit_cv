"""Ground partial participant fields in observed OCR words on the same text line."""

from .ocr_layout import line_groups
from .schema import TEXT_FIELDS, Box, OCRParticipant, Participant, TextField


def comparable_text(value: str) -> str:
    # Comparison only: field output always preserves the observed OCR spelling.
    return " ".join(token.strip('.,;:!?()[]{}\"„“').casefold() for token in value.split()).strip()


def line_key(word: dict) -> tuple | None:
    key = word.get("line")
    if isinstance(key, (list, tuple)) and len(key) == 3 and key[0] > 0 and key[2] > 0:
        return tuple(key)
    return None


def observed_spans(words: list[dict], value: str | None) -> list[list[int]]:
    if not value or not value.strip():
        return []
    target = comparable_text(value)
    if not target:
        return []
    spans = []
    for start in range(len(words)):
        for length in range(1, min(len(target.split()), len(words) - start) + 1):
            indices = list(range(start, start + length))
            observed = comparable_text(" ".join(words[i]["text"] for i in indices))
            if observed == target:
                spans.append(indices)
    return spans


def bounds(words: list[dict], indices: list[int]) -> Box:
    return Box(
        x0=min(words[i]["bbox"]["x0"] for i in indices),
        y0=min(words[i]["bbox"]["y0"] for i in indices),
        x1=max(words[i]["bbox"]["x1"] for i in indices),
        y1=max(words[i]["bbox"]["y1"] for i in indices),
    )


def same_row(words: list[dict], anchor: list[int], span: list[int]) -> bool:
    anchor_keys = {line_key(words[i]) for i in anchor}
    span_keys = {line_key(words[i]) for i in span}
    if None not in anchor_keys and None not in span_keys:
        if len(anchor_keys) == 1 and anchor_keys == span_keys:
            return True
        # Within one OCR block/paragraph, explicit distinct lines must not be merged by tall glyph boxes.
        if {key[:2] for key in anchor_keys} == {key[:2] for key in span_keys}:
            return False
    anchor_box, box = bounds(words, anchor), bounds(words, span)
    return min(anchor_box.y1, box.y1) > max(anchor_box.y0, box.y0)


def ground_partial_row(row: OCRParticipant, data: dict) -> tuple[Participant, list[dict]]:
    words = data["words"]
    matches = {name: observed_spans(words, getattr(row, name)) for name in TEXT_FIELDS}
    preferred = None
    if row.ocr_line_id is not None:
        groups = line_groups(data)
        if row.ocr_line_id > len(groups):
            raise ValueError("Modell nennt eine unbekannte OCR-Zeilenkennung")
        preferred = set(groups[row.ocr_line_id - 1])
    anchor = None
    for name in ("personnel_number", "last_name", "first_name"):
        candidates = [span for span in matches[name] if preferred is None or set(span).issubset(preferred)]
        if len(candidates) == 1:
            anchor = candidates[0]
            break
    if anchor is None:
        raise ValueError("Keine eindeutig lokalisierbare Personalnummer oder Namensangabe im OCR-Text")
    fields, evidence, warnings = {}, set(anchor), []
    for name in TEXT_FIELDS:
        value = getattr(row, name)
        if value is None:
            fields[name] = TextField(state="uncertain")
            continue
        same_line = [span for span in matches[name] if same_row(words, anchor, span)]
        if len(same_line) != 1:
            fields[name] = TextField(state="failed")
            reason = ("Wert nicht als vollständiges OCR-Wort oder Wortfolge vorhanden" if not matches[name]
                      else "Wortbeleg gehört zu einer anderen OCR-Zeile" if not same_line
                      else "Mehrere passende Wortbelege in derselben OCR-Zeile; Zuordnung mehrdeutig")
            warnings.append({"field": name, "reason": reason})
            continue
        span = same_line[0]
        evidence.update(span)
        observed_value = " ".join(words[i]["text"] for i in span)
        uncertain = any(words[i]["ocr_confidence"] is not None and words[i]["ocr_confidence"] < 30 for i in span)
        fields[name] = TextField(value=observed_value, state="uncertain" if uncertain else "read", bbox=bounds(words, span))
        if observed_value != value:
            warnings.append({"field": name, "reason": "Originalschreibweise der OCR-Wörter übernommen"})
        if uncertain:
            warnings.append({"field": name, "reason": "Niedrige OCR-Confidence; Feld manuell prüfen"})
    row_ref = None
    if row.row_ref:
        refs = [span for span in observed_spans(words, row.row_ref) if same_row(words, anchor, span)]
        if len(refs) == 1:
            row_ref = " ".join(words[i]["text"] for i in refs[0])
            evidence.update(refs[0])
        else:
            warnings.append({"field": "row_ref", "reason": "Gedruckte Zeilennummer nicht eindeutig in derselben OCR-Zeile belegt"})
    provided = set(row.word_ids)
    if (len(provided) != len(row.word_ids) or not evidence.issubset(provided)
            or any(i < 0 or i >= len(words) or not same_row(words, anchor, [i]) for i in provided)):
        warnings.append({"field": "word_ids", "reason": "Modellreferenzen passen nicht zu den Feldbelegen; Position aus OCR-Wörtern ermittelt"})
    if not any(field.value for field in fields.values()):
        raise ValueError("Keine belegbaren Teilnehmerfelder in der OCR-Zeile")
    notes = [f"{warning['field']}: {warning['reason']}" for warning in warnings]
    return Participant(row_ref=row_ref, bbox=bounds(words, sorted(evidence)),
                       **fields, review_notes=notes), warnings
