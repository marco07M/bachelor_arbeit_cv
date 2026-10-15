"""Descriptive evaluation; no ground truth is used by extraction or preprocessing."""

import unicodedata
from collections import Counter
from difflib import SequenceMatcher

import numpy as np
from scipy.optimize import linear_sum_assignment

from .schema import TEXT_FIELDS

DEFINITIONS = {
    "normalization": "NFC, whitespace collapse, casefold for names/department; personnel number exact raw string.",
    "matching": "Within document/page: unique printed row_ref; then vertical box IoU >=0.25; "
    "without both positions Hungarian name+department similarity >=0.65. Personnel number excluded.",
    "exact_match": "Correct known GT fields / all readable or empty GT fields, including missing rows. "
    "Illegible/uncertain GT excluded and counted separately.",
    "cer": "Micro sum Levenshtein edits / sum reference characters, by field. Missing rows predict empty. "
    "Extra-row characters are insertions. May exceed 1; zero denominator => null.",
    "field_prf": "TP=correct known field. Wrong known prediction FP+FN; missing/unknown FN. "
    "Extra-row known fields FP. Explicit empty is a known answer. Illegible GT excluded.",
    "entry_prf": "TP=matched row with all four known text fields correct. Incorrect matched row FP+FN. "
    "Rows with illegible GT excluded and counted. Extras FP, missing FN.",
    "assignment": "Match coverage and matching source, plus complete text rows. Content fallback approximate; "
    "not an independent identity verification.",
    "signature": "Known GT true/false only. Confusion matrix includes prediction unknown. Unknown positive "
    "is FN; coverage includes missing rows. Extra predicted true is FP. GT unknown excluded.",
    "scope": "Curated extraction uses selected page IDs. End-to-end uses all GT pages, including "
    "auto exclusions/failures. Unannotated output pages have no asserted quality.",
    "statistics": "Descriptive only. Fields/rows in the same document are dependent; no significance/winner score.",
}


def normalized(value, field):
    if value is None:
        return ""
    if field == "personnel_number":
        return value
    return " ".join(unicodedata.normalize("NFC", value).split()).casefold()


def known(field):
    return field.state in ("read", "empty")


def correct(prediction, truth, name):
    return (
        prediction is not None
        and known(prediction)
        and (normalized(prediction.value, name) == normalized(truth.value, name))
    )


def edits(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def vertical_iou(a, b):
    intersection = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    union = max(a.y1, b.y1) - min(a.y0, b.y0)
    return intersection / union if union else 0.0


def match_rows(predictions, truths):
    pairs = []
    pred_left, truth_left = set(range(len(predictions))), set(range(len(truths)))
    pc = Counter(p.row_ref for p in predictions if p.row_ref is not None)
    tc = Counter(t.row_ref for t in truths if t.row_ref is not None)
    for i, truth in enumerate(truths):
        if truth.row_ref is not None and tc[truth.row_ref] == pc[truth.row_ref] == 1:
            j = next(j for j, pred in enumerate(predictions) if pred.row_ref == truth.row_ref)
            pairs.append((j, i, "printed_row_ref"))
            pred_left.remove(j)
            truth_left.remove(i)
    pi, ti = sorted(pred_left), sorted(truth_left)
    if pi and ti:
        scores = np.zeros((len(pi), len(ti)))
        sources = {}
        for a, j in enumerate(pi):
            for b, i in enumerate(ti):
                pred, truth = predictions[j], truths[i]
                if pred.row_ref is not None and truth.row_ref is not None and pred.row_ref != truth.row_ref:
                    continue
                if pred.bbox and truth.bbox:
                    score = vertical_iou(pred.bbox, truth.bbox)
                    scores[a, b] = score if score >= 0.25 else 0.0
                    sources[a, b] = "position"
                else:
                    available = [
                        name
                        for name in ("first_name", "last_name", "department")
                        if known(getattr(truth, name)) and getattr(truth, name).value
                    ]
                    similarities = [
                        SequenceMatcher(
                            None,
                            normalized(getattr(pred, name).value, name),
                            normalized(getattr(truth, name).value, name),
                        ).ratio()
                        for name in available
                    ]
                    score = sum(similarities) / len(similarities) if similarities else 0.0
                    scores[a, b] = score if score >= 0.65 else 0.0
                    sources[a, b] = "content_fallback"
        rr, cc = linear_sum_assignment(-scores)
        for a, b in zip(rr, cc):
            if scores[a, b] > 0:
                j, i = pi[a], ti[b]
                pairs.append((j, i, sources[a, b]))
                pred_left.remove(j)
                truth_left.remove(i)
    return pairs, sorted(pred_left), sorted(truth_left)


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def prf(tp, fp, fn):
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def evaluate(results, ground_truth):
    by_page = {(r.document_id, r.page_number): r for r in results}
    fields = {name: Counter() for name in TEXT_FIELDS}
    signature, totals, matching_sources = Counter(), Counter(), Counter()
    details = []
    for page in ground_truth:
        result = by_page.get((page.document_id, page.page_number))
        predictions = result.participants if result else []
        truths = page.participants
        pairs, extras, missing = match_rows(predictions, truths)
        truth_to_pred = {i: (j, source) for j, i, source in pairs}
        totals.update(
            gt_pages=1,
            gt_rows=len(truths),
            prediction_rows=len(predictions),
            matched_rows=len(pairs),
            missing_rows=len(missing),
            extra_rows=len(extras),
            processed_pages=int(result is not None and result.parse_status == "valid"),
            technical_failure_pages=int(result is None or result.status in ("failed", "unavailable")),
            partial_pages=int(result is not None and result.status == "partial"),
            schema_failure_pages=int(result is not None and result.parse_status == "invalid"),
        )
        for i, truth in enumerate(truths):
            item = truth_to_pred.get(i)
            pred = predictions[item[0]] if item else None
            if item:
                matching_sources[item[1]] += 1
            row_correct, row_scorable = True, True
            for name in TEXT_FIELDS:
                gt_field = getattr(truth, name)
                p_field = getattr(pred, name) if pred else None
                counter = fields[name]
                if not known(gt_field):
                    counter["excluded_gt_unknown"] += 1
                    row_scorable = False
                    continue
                counter["denominator"] += 1
                counter["prediction_unknown"] += int(p_field is None or not known(p_field))
                same = correct(p_field, gt_field, name)
                counter["tp"] += int(same)
                counter["fn"] += int(not same)
                counter["fp"] += int(not same and p_field is not None and known(p_field))
                row_correct &= same
                reference = normalized(gt_field.value, name)
                predicted = normalized(p_field.value, name) if p_field else ""
                counter["edits"] += edits(reference, predicted)
                counter["reference_characters"] += len(reference)
                details.append(
                    {
                        "document_id": page.document_id,
                        "page_number": page.page_number,
                        "truth_index": i,
                        "truth_row_ref": truth.row_ref,
                        "prediction_index": item[0] if item else None,
                        "matching_source": item[1] if item else "missing",
                        "field": name,
                        "truth_raw": gt_field.value,
                        "prediction_raw": p_field.value if p_field else None,
                        "exact": same,
                    }
                )
            if row_scorable:
                totals["entry_tp"] += int(row_correct)
                totals["entry_fn"] += int(not row_correct)
                totals["entry_fp"] += int(not row_correct and pred is not None)
                totals["complete_matched_rows"] += int(row_correct and pred is not None)
            else:
                totals["entry_excluded_gt_unknown"] += 1
            gt_sig, p_sig = truth.signature_present, pred.signature_present if pred else None
            if gt_sig is None:
                signature["excluded_gt_unknown"] += 1
            else:
                signature["denominator"] += 1
                key = f"gt_{str(gt_sig).lower()}_pred_{'unknown' if p_sig is None else str(p_sig).lower()}"
                signature[key] += 1
                signature["unknown"] += int(p_sig is None)
                signature["tp"] += int(gt_sig is True and p_sig is True)
                signature["fp"] += int(gt_sig is False and p_sig is True)
                signature["fn"] += int(gt_sig is True and p_sig is not True)
                signature["tn"] += int(gt_sig is False and p_sig is False)
        for j in extras:
            pred = predictions[j]
            totals["entry_fp"] += 1
            for name in TEXT_FIELDS:
                field = getattr(pred, name)
                fields[name]["fp"] += int(known(field))
                fields[name]["edits"] += len(normalized(field.value, name))
            if pred.signature_present is True:
                signature["fp"] += 1
                signature["extra_positive"] += 1
            details.append(
                {
                    "document_id": page.document_id,
                    "page_number": page.page_number,
                    "prediction_index": j,
                    "matching_source": "extra",
                }
            )
    scores = {}
    for name, counts in fields.items():
        scores[name] = {
            "exact_match": ratio(counts["tp"], counts["denominator"]),
            "cer": ratio(counts["edits"], counts["reference_characters"]),
            "prf": prf(counts["tp"], counts["fp"], counts["fn"]),
            "unknown_rate": ratio(counts["prediction_unknown"], counts["denominator"]),
            "coverage": ratio(counts["denominator"] - counts["prediction_unknown"], counts["denominator"]),
            "excluded_gt_unknown": counts["excluded_gt_unknown"],
        }
    all_counts = sum(fields.values(), Counter())
    return {
        "counts": dict(totals),
        "fields": scores,
        "overall_exact_match": ratio(all_counts["tp"], all_counts["denominator"]),
        "field_prf": prf(all_counts["tp"], all_counts["fp"], all_counts["fn"]),
        "entry_prf": prf(totals["entry_tp"], totals["entry_fp"], totals["entry_fn"]),
        "assignment": {
            "match_coverage": ratio(totals["matched_rows"], totals["gt_rows"]),
            "complete_row_coverage": ratio(totals["complete_matched_rows"], totals["gt_rows"]),
            "matching_sources": dict(matching_sources),
        },
        "signature": {
            "prf": prf(signature["tp"], signature["fp"], signature["fn"]),
            "confusion": {
                f"gt_{gt}_pred_{pred}": signature[f"gt_{gt}_pred_{pred}"]
                for gt in ("true", "false")
                for pred in ("true", "false", "unknown")
            },
            "unknown_rate": ratio(signature["unknown"], signature["denominator"]),
            "coverage": ratio(signature["denominator"] - signature["unknown"], signature["denominator"]),
            "excluded_gt_unknown": signature["excluded_gt_unknown"],
            "extra_positive": signature["extra_positive"],
        },
        "definitions": DEFINITIONS,
    }, details


def evaluate_groups(results, ground_truth):
    aggregate, details = evaluate(results, ground_truth)
    grouped = {}
    for attribute in ("split", "content_type"):
        grouped[attribute] = {}
        for value in sorted({getattr(page, attribute) for page in ground_truth}):
            subset = [page for page in ground_truth if getattr(page, attribute) == value]
            grouped[attribute][value] = evaluate(results, subset)[0]
    return {"aggregate": aggregate, "groups": grouped}, details
