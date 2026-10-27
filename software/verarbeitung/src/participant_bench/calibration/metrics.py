"""Separate raw text, structured fields, assignment and visual signature metrics."""

import unicodedata
from collections import Counter
from pathlib import Path

from ..evaluation import edits, evaluate, known, match_rows, normalized, ratio
from ..io import read_json, read_jsonl
from ..ocr_evidence import observed_spans
from ..ocr_layout import readable_text
from ..schema import TEXT_FIELDS, PageResult


def text_metrics(reference: str, prediction: str) -> dict:
    return {
        "cer": ratio(edits(reference, prediction), len(reference)),
        "wer": ratio(edits(reference.split(), prediction.split()), len(reference.split())),
    }


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def field_score(field, person, data: dict) -> float | None:
    if not field.value or data.get("text_source") == "pdf_text":
        return None
    words, box = data.get("words", []), field.bbox or person.bbox
    spans = observed_spans(words, field.value)
    if box:
        spans = [
            span
            for span in spans
            if all(
                box.x0 <= (words[i]["bbox"]["x0"] + words[i]["bbox"]["x1"]) / 2 <= box.x1
                and box.y0 <= (words[i]["bbox"]["y0"] + words[i]["bbox"]["y1"]) / 2 <= box.y1
                for i in span
            )
        ]
    if len(spans) != 1:
        return None
    scores = [words[i].get("ocr_confidence") for i in spans[0]]
    if any(score is None or not 0 <= score <= 100 for score in scores):
        return None
    return min(scores) / 100


def assess(run: Path, method: str, truths: list, reference_texts: dict, quality_flags: dict) -> dict:
    results = [PageResult.model_validate(row) for row in read_jsonl(run / method / "extractions.jsonl")]
    aggregate, _ = evaluate(results, truths)
    by_page = {(page.document_id, page.page_number): page for page in results}
    events, errors, texts, durations, normalized_fields = [], [], [], [], []
    for truth in truths:
        key = (truth.document_id, truth.page_number)
        result = by_page.get(key)
        predictions = result.participants if result else []
        for index, person in enumerate(predictions):
            for name in TEXT_FIELDS:
                field = getattr(person, name)
                normalized_fields.append(
                    dict(
                        document_id=key[0],
                        page_number=key[1],
                        prediction_index=index,
                        field=name,
                        raw_value=field.value,
                        normalized_value=normalized(field.value, name) if field.value is not None else None,
                        state=field.state,
                        bbox=field.bbox.model_dump() if field.bbox else None,
                    )
                )
        raw_path = run / method / f"raw-{truth.document_id}-p{truth.page_number:04d}.json"
        raw = read_json(raw_path) if raw_path.exists() else {}
        data = raw.get("ocr", {})
        observed_text = readable_text(data)
        if key in reference_texts:
            texts.append(
                {
                    "document_id": key[0],
                    "page_number": key[1],
                    "raw": text_metrics(reference_texts[key], observed_text),
                    "normalized": text_metrics(
                        normalize_text(reference_texts[key]), normalize_text(observed_text)
                    ),
                }
            )
        timings = result.timings if result else {}
        durations.append({"document_id": key[0], "page_number": key[1], **timings})
        pairs, extras, missing = match_rows(predictions, truth.participants)
        mapping = {i: (j, source) for j, i, source in pairs}
        for flag in quality_flags.get(key, []):
            errors.append(
                dict(
                    document_id=key[0],
                    page_number=key[1],
                    category="manual_quality_flag",
                    flag=flag,
                    evidence="manual",
                )
            )
        for i, person in enumerate(truth.participants):
            item = mapping.get(i)
            predicted = predictions[item[0]] if item else None
            for name in TEXT_FIELDS:
                field = getattr(person, name)
                if not known(field):
                    continue
                value = getattr(predicted, name) if predicted else None
                same = (
                    value is not None
                    and value.value is not None
                    and normalized(value.value, name) == normalized(field.value, name)
                )
                event = dict(
                    document_id=key[0],
                    dependency_group=truth.dependency_group,
                    page_number=key[1],
                    truth_index=i,
                    prediction_index=item[0] if item else None,
                    field=name,
                    correct=int(same),
                    raw_score=field_score(value, predicted, data) if value else None,
                    has_value=value is not None and value.value is not None,
                    ground_truth_empty=not bool(field.value),
                    predicted_nonempty=bool(value and value.value),
                    matching_source=item[1] if item else "missing",
                )
                events.append(event)
                if not same:
                    if predicted is None or value is None or value.value is None:
                        category = "missing_extraction"
                    elif field.value and normalize_text(field.value) not in normalize_text(observed_text):
                        category = "ocr_recognition"
                    else:
                        category = "field_extraction_or_assignment"
                    confusion = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})
                    if (
                        value
                        and value.value
                        and field.value
                        and value.value != field.value
                        and value.value.translate(confusion) == field.value.translate(confusion)
                    ):
                        category = "similar_character_confusion"
                    if (
                        value
                        and value.value
                        and field.value
                        and len(value.value) < len(field.value)
                        and edits(value.value, field.value) == len(field.value) - len(value.value)
                    ):
                        category = "possible_missing_characters"
                    if (
                        value
                        and value.value
                        and any(
                            other is not person
                            and getattr(other, name).value
                            and normalized(getattr(other, name).value, name) == normalized(value.value, name)
                            for other in truth.participants
                        )
                    ):
                        category = "possible_wrong_person_assignment"
                    errors.append(
                        {k: event[k] for k in ("document_id", "page_number", "truth_index", "field")}
                        | {"category": category, "evidence": "heuristic"}
                    )
            if person.signature_present is not None and (
                predicted is None or person.signature_present != predicted.signature_present
            ):
                errors.append(
                    dict(
                        document_id=key[0],
                        page_number=key[1],
                        truth_index=i,
                        category="signature_presence",
                        evidence="manual_reference",
                    )
                )
        for j in extras:
            for name in TEXT_FIELDS:
                field = getattr(predictions[j], name)
                if field.value is not None:
                    events.append(
                        dict(
                            document_id=key[0],
                            page_number=key[1],
                            truth_index=None,
                            prediction_index=j,
                            dependency_group=truth.dependency_group,
                            field=name,
                            correct=0,
                            raw_score=field_score(field, predictions[j], data),
                            has_value=True,
                            ground_truth_empty=False,
                            predicted_nonempty=bool(field.value),
                            matching_source="extra",
                        )
                    )
            errors.append(
                dict(
                    document_id=key[0],
                    page_number=key[1],
                    prediction_index=j,
                    category="extra_extraction",
                    evidence="matching",
                )
            )
        refs = Counter(p.row_ref for p in predictions if p.row_ref)
        if any(count > 1 for count in refs.values()):
            errors.append(
                dict(
                    document_id=key[0],
                    page_number=key[1],
                    category="possible_duplicate_row",
                    evidence="repeated_row_ref",
                )
            )
    for field in TEXT_FIELDS:
        samples = [event for event in events if event["field"] == field]
        scores = aggregate["fields"][field]
        prf = scores["prf"]
        scores["false_discovery_rate"] = ratio(prf["fp"], prf["tp"] + prf["fp"])
        scores["false_negative_rate"] = ratio(prf["fn"], prf["tp"] + prf["fn"])
        empty = [event for event in samples if event["ground_truth_empty"]]
        scores["empty_cell_false_positive_rate"] = ratio(
            sum(event["predicted_nonempty"] for event in empty), len(empty)
        )
    text_summary = {}
    for kind in ("raw", "normalized"):
        text_summary[kind] = {
            metric: ratio(
                sum(item[kind][metric]["numerator"] for item in texts),
                sum(item[kind][metric]["denominator"] for item in texts),
            )
            for metric in ("cer", "wer")
        }
    return dict(
        structured=aggregate,
        text=dict(pages_with_manual_text=len(texts), **text_summary),
        events=events,
        errors=errors,
        text_pages=texts,
        page_timings=durations,
        normalized_fields=normalized_fields,
        error_counts=dict(Counter(row["category"] for row in errors)),
        score_definition="Minimum Tesseract word confidence / 100 over unique field evidence; uncalibrated score, not probability. PDF text, empty or ambiguous evidence: no score.",
    )
