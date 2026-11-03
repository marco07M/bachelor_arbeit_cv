"""Paired field transitions against frozen ground truth, not word-set agreement."""

import html
from collections import Counter, defaultdict

import yaml

from .evaluation import edits
from .io import read_json, write_csv, write_json
from .output_order import document_order, ordered_rows

VERSION = "paired-image-ocr-v2-reference-states"


def comparison_controls(source):
    """Check frozen model settings and actual per-page input hashes; do not load a model."""
    config_path = source / "config.yaml"
    if not config_path.is_file():
        return dict(verified=False, reason="No frozen extraction configuration")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    models = config.get("models", {})
    same_model = bool(models.get("vlm") and models.get("vlm") == models.get("ocr_vlm"))
    images, versions = {}, {}
    for method in ("vlm", "ocr_vlm"):
        images[method], versions[method] = {}, set()
        for path in (source / method).glob("raw-*.json"):
            record = read_json(path)
            images[method][record["page_id"]] = record.get("run_image_sha256")
            versions[method].update(item.get("prompt_version") for item in record.get("responses", []))
    same_images = bool(images["vlm"] and images["vlm"] == images["ocr_vlm"] and all(images["vlm"].values()))
    same_prompt = bool(versions["vlm"] and None not in versions["vlm"] and versions["vlm"] == versions["ocr_vlm"])
    return dict(verified=same_model and same_images and same_prompt, identical_vlm_settings=same_model,
                identical_page_images=same_images, identical_base_prompt_version=same_prompt,
                generative_model=models.get("vlm", {}).get("repo"))


def compare_fields(baseline, hybrid, *, key_fields, normalize, source="ground_truth"):
    def indexed(records):
        result = {}
        for item in records:
            if (item.get(key_fields[-1]) is None or item.get("exclusion_reason") == "reference_missing_or_masked"
                    or item.get("reference_state") == "empty"):
                continue
            key = tuple(item.get(field) for field in (*key_fields, "field"))
            if key in result:
                raise ValueError("Doppelte Referenzfeldkennung in der Hybridanalyse")
            result[key] = item
        return result
    left, right = indexed(baseline), indexed(hybrid)
    totals, rows, records = Counter(fields=0, corrected=0, regressed=0, both_correct=0, both_incorrect=0), [], defaultdict(list)
    for key in sorted(left.keys() | right.keys(), key=str):
        before, after = left.get(key, {}), right.get(key, {})
        template = before or after
        expected = template.get("truth_raw", template.get("reference_value"))
        if before and after and before.get("truth_raw", before.get("reference_value")) != after.get("truth_raw", after.get("reference_value")):
            raise ValueError("VLM und Hybrid wurden nicht gegen dieselbe Referenz verglichen")
        a = before.get("prediction_raw", before.get("prediction_value"))
        b = after.get("prediction_raw", after.get("prediction_value"))
        field = template["field"]
        reference_text = normalize(expected, field)
        a_text, b_text = normalize(a, field), normalize(b, field)
        correct_a, correct_b = before.get("exact") is True, after.get("exact") is True
        transition = ("both_correct" if correct_a and correct_b else "corrected" if correct_b else
                      "regressed" if correct_a else "both_incorrect")
        da, db = edits(reference_text, a_text), edits(reference_text, b_text)
        totals.update(fields=1, **{transition: 1}, baseline_correct=int(correct_a), hybrid_correct=int(correct_b),
                      baseline_edits=da, hybrid_edits=db, reference_characters=len(reference_text))
        records[key[:-1]].append((correct_a, correct_b))
        rows.append(dict(zip((*key_fields, "field"), key), reference_value=expected,
                         vlm_value=a, ocr_vlm_value=b, vlm_exact=correct_a, ocr_vlm_exact=correct_b,
                         vlm_distance=da, ocr_vlm_distance=db, transition=transition))
        location = before if before.get("output_index", before.get("prediction_index")) not in (None, "") else after
        for name in ("document_id", "page_number", "output_index"):
            if name not in rows[-1]:
                rows[-1][name] = location.get(name, location.get("prediction_index") if name == "output_index" else None)
    count, chars, record_count = totals["fields"], totals["reference_characters"], len(records)
    def value(n, d):
        return n/d if d else None
    result = dict(version=VERSION, status="measured" if count else "not_measured", source=source,
        counts=dict(totals), baseline_field_exact=value(totals["baseline_correct"], count),
        hybrid_field_exact=value(totals["hybrid_correct"], count),
        baseline_paired_cer=value(totals["baseline_edits"], chars), hybrid_paired_cer=value(totals["hybrid_edits"], chars),
        evaluated_records=record_count,
        baseline_record_accuracy=value(sum(all(a for a, _ in fields) for fields in records.values()), record_count),
        hybrid_record_accuracy=value(sum(all(b for _, b in fields) for fields in records.values()), record_count),
        definition="Same reference participant/field, with existing matching and normalization. Record accuracy uses all "
                   "assessable reference fields of that record. Paired CER excludes unmatched extra predictions; "
                   "the ordinary per-method metrics retain their extra-row penalties. A non-exact ID remains incorrect.")
    by_field = {}
    for row in rows:
        counters = by_field.setdefault(row["field"], Counter(fields=0, corrected=0, regressed=0,
            both_correct=0, both_incorrect=0, missing_values_recovered=0, new_missing_values=0))
        counters.update(fields=1, **{row["transition"]: 1})
        before = normalize(row["vlm_value"], row["field"])
        after = normalize(row["ocr_vlm_value"], row["field"])
        counters["missing_values_recovered"] += int(not before and bool(after))
        counters["new_missing_values"] += int(bool(before) and not after)
    result["per_field"] = {field: dict(counters) for field, counters in by_field.items()}
    return result, rows


def export_analysis(output, analysis, rows, *, summaries=None, source=None):
    if source and (source / "manifest.json").is_file():
        rows = ordered_rows(rows, document_order(read_json(source / "manifest.json")))
    summaries = summaries or {}
    a, b = summaries.get("vlm", {}), summaries.get("ocr_vlm", {})
    def delta(key):
        return b[key]-a[key] if isinstance(a.get(key), (float, int)) and isinstance(b.get(key), (float, int)) else None
    analysis = dict(analysis, runtime_delta_seconds=delta("actual_method_wall_seconds"),
                    charged_runtime_delta_seconds=delta("full_pipeline_charged_seconds"),
                    baseline_runtime_seconds=a.get("actual_method_wall_seconds"),
                    hybrid_runtime_seconds=b.get("actual_method_wall_seconds"),
                    baseline_charged_seconds=a.get("full_pipeline_charged_seconds"),
                    hybrid_charged_seconds=b.get("full_pipeline_charged_seconds"),
                    comparison_controls=comparison_controls(source) if source else dict(verified=False, reason="No frozen source supplied"))
    write_json(output / "hybrid_analysis.json", analysis)
    write_csv(output / "hybrid_fields.csv", rows, fields=list(rows[0]) if rows else ["field", "transition"])
    def esc(value):
        return html.escape(str(value), quote=True)
    facts = "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in analysis.items() if k != "counts")
    counts = "".join(f"<li>{esc(k)}: {esc(v)}</li>" for k, v in analysis.get("counts", {}).items())
    headings = list(rows[0]) if rows else []
    table = "".join("<tr>"+"".join(f"<td>{esc(row.get(k))}</td>" for k in headings)+"</tr>" for row in rows[:5000])
    text = ('<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>VLM und OCR-VLM vergleichen</title><style>body{font:15px system-ui;margin:2rem}table{border-collapse:collapse;'
            'display:block;overflow:auto}th,td{border:1px solid #bbb;padding:.5rem;text-align:left}td{white-space:pre-wrap}</style>'
            '<h1>Bild-only-VLM gegenüber Bild plus Paddle-OCR</h1><p><a href="report.html">Zur Übersicht</a></p>'
            '<p>corrected: zuvor falsch, jetzt exakt; regressed: zuvor exakt, jetzt falsch. Änderungen werden pro '
            'zugeordneter Referenzperson bewertet. Ohne Ground Truth wird keine Verbesserung behauptet.</p>'
            f'<table>{facts}</table><ul>{counts}</ul><p><a href="hybrid_fields.csv">Alle Feldvergleiche als CSV</a> · '
            '<a href="hybrid_analysis.json">Metriken als JSON</a>. HTML-Anzeige maximal 5000 Feldvergleiche.</p>'
            '<table><tr>'+"".join(f"<th>{esc(k)}</th>" for k in headings)+f'</tr>{table}</table></html>')
    (output / "hybrid_analysis.html").write_text(text, encoding="utf-8")
    return analysis
