"""Post-hoc text evaluation against independently reviewed page transcripts; no inference or fitting."""

import csv
from pathlib import Path

from .calibration.metrics import normalize_text, text_metrics
from .evaluation import ratio
from .io import digest, file_hash, read_json, read_jsonl, write_csv, write_json
from .schema import PageResult


def evaluate_text(run: Path, references: Path, method="unlimited_ocr"):
    predictions = {
        (page.document_id, page.page_number): page
        for page in (PageResult.model_validate(row) for row in read_jsonl(run / method / "extractions.jsonl"))
    }
    with (references / "pages.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    scores, hashes, seen = [], {"pages.csv": file_hash(references / "pages.csv")}, set()
    input_documents = {
        item["sha256"]
        for item in read_json(run / "manifest.json")["inputs"]
        if item["kind"] in ("pdf", "image")
    }
    outside_scope = 0
    for row in rows:
        if row["text_reviewed"].casefold() != "true":
            continue
        key = row["document_id"], int(row["page_number"])
        if key[0] not in input_documents:
            outside_scope += 1
            continue
        if key in seen:
            raise ValueError("Doppelte Textreferenz für dieselbe Seite")
        seen.add(key)
        source = (references / row["reference_text_file"]).resolve()
        if not source.is_relative_to(references.resolve()):
            raise ValueError("Textreferenz muss innerhalb des Referenzordners liegen")
        truth = source.read_text(encoding="utf-8-sig")
        hashes[row["reference_text_file"]] = file_hash(source)
        predicted = predictions.get(key)
        text = predicted.page_text or "" if predicted else ""
        scores.append(
            dict(
                document_id=key[0],
                page_number=key[1],
                prediction_present=predicted is not None,
                original=text_metrics(truth, text),
                normalized=text_metrics(normalize_text(truth), normalize_text(text)),
            )
        )
    if not scores:
        raise ValueError("Keine mit text_reviewed=true bestätigten Seitentranskripte gefunden")
    summary = dict(
        method=method,
        reference_version=digest(hashes),
        reference_hashes=hashes,
        prediction_hash=file_hash(run / method / "extractions.jsonl"),
        pages=len(scores),
        reference_pages_outside_input_documents=outside_scope,
        unreferenced_prediction_pages=len(set(predictions) - seen),
        missing_prediction_pages=sum(not row["prediction_present"] for row in scores),
        scope="OCR text only, no field accuracy; original spelling retained, NFC/whitespace separately normalized",
    )
    for kind in ("original", "normalized"):
        summary[kind] = {
            name: ratio(
                sum(row[kind][name]["numerator"] for row in scores),
                sum(row[kind][name]["denominator"] for row in scores),
            )
            for name in ("cer", "wer")
        }
    target = run / method / "text_evaluation"
    write_json(target / "metrics.json", summary)
    write_csv(
        target / "pages.csv",
        [
            dict(
                document_id=row["document_id"],
                page_number=row["page_number"],
                prediction_present=row["prediction_present"],
                **{
                    f"{k}_{m}": row[k][m]["value"] for k in ("original", "normalized") for m in ("cer", "wer")
                },
            )
            for row in scores
        ],
    )
    return target
