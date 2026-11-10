"""Local, evidence-limited loss analysis of frozen grading and extraction artifacts.

References enter only this presentation step. They never repair extraction or
locate unmatched course references on a guessed PDF page.
"""

import json
import os
from collections import Counter
from pathlib import Path

from ..config import METHODS
from ..io import digest, file_hash, read_json, read_jsonl, write_json
from ..ocr_observations import audit
from ..schema import PageResult
from .detail_report import document, esc, read_csv, table, truth
from .matching import FIELDS

VERSION = "extraction-error-analysis-v1"
CATEGORIES = {
    "none": "Kein bewerteter Feldfehler", "unknown": "Ursache unbekannt",
    "name_swap": "Vor-/Nachname-Vertauschung (Swap)",
    "validation": "Beleg-/Positionsvalidierung", "column_mapping": "Fehlende Spaltenzuordnung",
    "not_submitted": "OCR-Beleg nicht an Zuordnung übergeben",
    "model_omission": "Erkannter Text ohne Feldübernahme",
    "ocr_suspected": "OCR-Lesefehler oder falsche Zuordnung vermutet",
    "extra": "Zusätzliche Ausgabe", "unassessed": "Nicht bewertbar",
}
STATUSES = {"correct": "Korrekt", "incorrect": "Falsch", "missing": "Fehlend",
            "extra": "Zusätzlich", "unassessed": "Nicht bewertbar"}
CERTAINTY = {"proven": "Nachgewiesen", "hypothesis": "Vermutung", "unknown": "Unbekannt"}
SCRIPT = """(() => {
const ids=['method','page','field','category','certainty','result'];
const controls=ids.map(id=>document.getElementById(id));
const search=document.getElementById('search');
const apply=()=>{let count=0;
for(const card of document.querySelectorAll('article.field-case')){
const show=ids.every((id,i)=>!controls[i].value||card.dataset[id]===controls[i].value)&&
card.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
card.hidden=!show;if(show)count++;}
for(const section of document.querySelectorAll('section.page-analysis')){
const method=controls[0].value,page=controls[1].value;
section.hidden=!!((method&&section.dataset.method!==method)||(page&&section.dataset.page!==page));}
document.getElementById('visible-count').textContent=String(count);};
for(const control of [...controls,search])control.addEventListener('input',apply);apply();
})();"""


def field_status(row):
    if row.get("reference_contribution") == "1":
        if truth(row.get("exact")):
            return "correct"
        return "missing" if not row.get("normalized_prediction") or row.get("exclusion_reason") == "invalid_prediction_placeholder" else "incorrect"
    return "extra" if row.get("prediction_contribution") == "1" else "unassessed"


def source_field(row):
    field = row["field"]
    if truth(row.get("name_swapped")):
        field = {"first_name": "last_name", "last_name": "first_name"}.get(field, field)
    return FIELDS[field]


def overlaps(left, right):
    return bool(left and right and min(left["x1"], right["x1"]) > max(left["x0"], right["x0"]) and
                min(left["y1"], right["y1"]) > max(left["y0"], right["y0"]))


def row_proof(raw, index):
    proofs = raw.get("structure", {}).get("row_evidence", []) or [
        p for r in raw.get("responses", []) for p in r.get("ocr_field_evidence", [])]
    # Exclusions can change output indices. Never attach an earlier person's proof by index alone.
    role_filter = raw.get("person_role_filter", {})
    if role_filter.get("excluded"):
        indices = [m["source_output_index"] for m in role_filter.get("output_index_mapping", []) if m["output_index"] == index]
        if len(indices) != 1:
            return {}
        index = indices[0]
    matches = [p for p in proofs if p.get("output_index") == index]
    return matches[0] if len(matches) == 1 else {}


def diagnose_field(row, page=None, raw=None, ledger=None):
    """Attribute only saved, local stage transitions; a missing GT string is not OCR failure."""
    raw, ledger = raw or {}, ledger or {}
    status, field = field_status(row), source_field(row)
    name_swapped = bool(truth(row.get("name_swapped")))
    result = dict(result=status, category="unknown", certainty="unknown", stage="unknown",
                  name_swapped=name_swapped,
                  reason="Die gespeicherten Daten belegen keine eindeutige Fehlerursache.", evidence=[], observations=[])
    if not page or not row.get("output_index"):
        # CSV output_index '0' is truthy; missing reference rows have an empty index.
        result["reason"] = ("Kursreferenz ohne Seitenlokalisierung: keine Zuordnung zu einer PDF-Seite oder OCR-Zeile "
                            "belegt. Kein Rückschluss auf fehlende OCR-Erkennung möglich.")
        if status in ("unassessed", "extra"):
            result.update(category=status, reason="Kein bewertbarer lokalisierter Referenzvergleich.")
        return result
    index = int(row["output_index"])
    if index >= len(page.participants):
        return result
    person, proof = page.participants[index], row_proof(raw, index)
    target = getattr(person, field)
    field_proof = proof.get("fields", {}).get(field, {})
    region = target.bbox.model_dump() if target.bbox else person.bbox.model_dump() if person.bbox else None
    cells = proof.get("source_cells", [])
    row_boxes = [c["bbox"] for c in cells if c.get("bbox")]
    if not region and row_boxes:
        region = {k: op(b[k] for b in row_boxes) for k, op in (("x0", min), ("x1", max), ("y0", min), ("y1", max))}
    related = [o for o in ledger.get("observations", []) if overlaps(region, o.get("bbox"))]
    provenance = field_proof.get("provenance") or proof.get("provenance")
    result.update(
        observations=related,
        bbox=region,
        source_row=proof.get("source_row"),
        field_proof=field_proof,
        provenance=provenance,
        original_docling_value=field_proof.get("original_docling_value"),
    )
    if status in ("correct", "unassessed", "extra"):
        reason = "Gespeicherter Feldvergleich; die Referenzpaarung ist keine unabhängige Identitätsprüfung."
        if name_swapped and row.get("field") in ("first_name", "last_name"):
            reason += " Vor-/Nachnamensrollen wurden im Referenzvergleich über die Swap-Toleranz abgeglichen (Originalausgabe war vertauscht)."
        result.update(category="none" if status == "correct" else status, certainty="proven", stage="evaluation",
                      reason=reason)
        return result
    expected = str(row.get("reference_value") or "").strip()
    if status == "incorrect" and field in ("first_name", "last_name") and expected:
        opposite_field = "last_name" if field == "first_name" else "first_name"
        opposite_val = str(getattr(person, opposite_field).value or "").strip()
        if opposite_val and opposite_val.casefold() == expected.casefold():
            result.update(
                category="name_swap",
                certainty="proven",
                stage="name_role_assignment",
                name_swapped=True,
                reason="Vor- und Nachname sind in der Vorhersage gegenüber der Referenz vertauscht (Swap-Fehler).",
            )
            return result
    if target.state == "failed" or field_proof.get("rejected"):
        notes = [n for n in person.review_notes if field in n]
        result.update(category="validation", certainty="proven", stage="validation",
            reason="Das Feld wurde als fehlgeschlagen markiert. Dies belegt die Ablehnung, nicht die Richtigkeit des Vorschlags.",
            evidence=[field_proof.get("rejected"), *notes])
        return result
    mapping = raw.get("structure", {}).get("mapping_diagnostics", [])
    if status == "missing" and mapping and proof.get("fallback") and field == "department":
        result.update(category="column_mapping", certainty="proven", stage="native_mapper",
            reason="Der native Teilpersonen-Fallback übernimmt ohne eindeutige Überschrift keine Organisationsspalte.",
            evidence=[m.get("reason") for m in mapping])
        return result
    # Reference is used here only to explain the already frozen output. No global
    # search or fuzzy association to a different person/page is allowed.
    text = " ".join(str(o["text"]) for o in related)
    local_literal = bool(expected and (any(expected == str(o["text"]).strip() for o in related) or
                                     expected in text.split("\n")))
    if status == "missing" and local_literal:
        submitted = [o.get("submitted_to_assignment") for o in related if expected == str(o["text"]).strip()]
        if submitted and all(v is False for v in submitted):
            result.update(category="not_submitted", certainty="proven", stage="input_selection",
                reason="Der wörtliche Referenztext liegt im zugeordneten Quellbereich, wurde aber laut Wortbelegen nicht übergeben.")
        elif submitted and all(v is True for v in submitted) and target.value is None:
            result.update(category="model_omission", certainty="proven", stage="assignment",
                reason="Der wörtliche Referenztext wurde aus diesem Quellbereich übergeben; im finalen Feld steht kein Wert. "
                       "Die innere Modellentscheidung ist nicht gespeichert.")
        return result
    if status == "incorrect" and related and target.value and any(
            str(target.value) in str(o["text"]) or str(o["text"]) in str(target.value) for o in related):
        result.update(category="ocr_suspected", certainty="hypothesis", stage="recognition_or_assignment",
            reason="Die Ausgabe ist wörtlich in OCR-Belegen dieses Quellbereichs enthalten, weicht aber von der Referenz ab. "
                   "OCR-Lesefehler, falsche Feld-/Personenzuordnung und Referenzabweichung sind ohne geprüfte Lokalisierung nicht trennbar.")
    return result


def relative_link(path, output):
    return Path(os.path.relpath(path, output)).as_posix()


def crop(source, output, page, box, key):
    """Only a saved extraction region, never a GT-derived bounding box."""
    if not box or not all(isinstance(box.get(k), (float, int)) and 0 <= box[k] <= 1 for k in ("x0", "x1", "y0", "y1")):
        return None
    if box["x1"] <= box["x0"] or box["y1"] <= box["y0"]:
        return None
    image_path = (source / "pages" / (page.page_id + ".png")).resolve()
    if not image_path.is_relative_to((source / "pages").resolve()) or not image_path.is_file():
        return None
    from PIL import Image

    path = output / "error_analysis" / (digest(key)[:20] + ".png")
    if not path.is_file():
        with Image.open(image_path) as image:
            w, h = image.size
            image.crop((max(0, int(box["x0"]*w)-5), max(0, int(box["y0"]*h)-5),
                        min(w, int(box["x1"]*w)+6), min(h, int(box["y1"]*h)+6))).save(path)
    return relative_link(path, output)


def select(name, title, values):
    return f'<label>{esc(title)} <select id="{esc(name)}"><option value="">Alle</option>' + "".join(
        f'<option value="{esc(key)}">{esc(label)}</option>' for key, label in values) + '</select></label>'


def render_errors(output: Path, *, source_run: Path | None = None) -> Path:
    """Render saved scores and evidence. No extraction, reference reload or scoring."""
    output = output.resolve()
    identity, metrics = read_json(output / "identity.json"), read_json(output / "metrics.json")
    source = Path(source_run or identity["source_run"]).resolve()
    fields = read_csv(output / "fields.csv")
    from ..output_order import document_order, ordered_rows

    manifest = read_json(source / "manifest.json") if (source / "manifest.json").is_file() else {}
    fields = ordered_rows(fields, document_order(manifest), {m: i for i, m in enumerate(metrics["methods"])})
    pages, raw_pages, ledgers, paths = {}, {}, {}, {}
    unavailable = []
    folder = output / "error_analysis"
    folder.mkdir(exist_ok=True)
    for method in metrics["methods"]:
        if method not in {*METHODS, "ocr_rules"}:
            raise ValueError("Unbekanntes Verfahren im gespeicherten Vergleich")
        extraction = source / method / "extractions.jsonl"
        if not extraction.is_file():
            unavailable.append(method)
            continue
        expected_hash = identity.get("extraction_sha256", {}).get(method)
        if expected_hash is not None and file_hash(extraction) != expected_hash:
            raise ValueError("Quellvorhersagen wurden seit dem gespeicherten Vergleich verändert")
        if expected_hash is None and metrics["methods"][method].get("status") != "not_applicable":
            unavailable.append(method)
            continue
        for record in read_jsonl(extraction):
            page = PageResult.model_validate(record)
            key = method, page.document_id, str(page.page_number)
            pages[key] = page
            raw_path = (source / method / ("raw-"+page.page_id+".json")).resolve()
            if not raw_path.is_relative_to(source / method):
                raise ValueError("Ungültiger lokaler Rohdatenpfad")
            raw = read_json(raw_path) if raw_path.is_file() else {}
            raw_pages[key], ledgers[key] = raw, audit(raw, page)
            paths[key] = raw_path if raw_path.is_file() else None
    cards, records, counts, categories = [], [], Counter(), Counter()
    page_values = [("unknown", "Seite unbekannt (Kursreferenz)")]
    names = {item.get("sha256"): Path(item.get("path", "")).name for item in manifest.get("inputs", [])}
    for key, page in pages.items():
        value = f"{page.document_id}:{page.page_number}"
        if not any(v == value for v, _ in page_values):
            page_values.append((value, f"{names.get(page.document_id) or page.document_id[:12]} · PDF-Seite {page.page_number}"))
    for row in fields:
        key = row["method"], row.get("document_id"), row.get("page_number")
        page = pages.get(key)
        finding = diagnose_field(row, page, raw_pages.get(key), ledgers.get(key))
        status, category, certainty = (finding[n] for n in ("result", "category", "certainty"))
        counts[row["method"], status] += 1
        categories[category, certainty] += 1
        page_id = f"{row['document_id']}:{row['page_number']}" if row.get("page_number") else "unknown"
        title = f"{row['method']} · {row.get('source_file') or names.get(row.get('document_id')) or row.get('class_id')} · " + (f"PDF-Seite {row['page_number']} · Ausgabezeile {int(row['output_index'])+1} · Referenzzeile {row.get('reference_row') or '—'}"
            if row.get("output_index") else f"Seite unbekannt · Referenzzeile {row.get('reference_row')}")
        card = ('<article class="field-case" ' + " ".join(f'data-{k}="{esc(v)}"' for k, v in
            dict(method=row["method"], page=page_id, field=row["field"], category=category, certainty=certainty, result=status).items()) +
            f'><h3>{esc(title)} · {esc(row.get("field_label") or row["field"])}</h3>')
        card += table(["Referenz (eingefroren)", "Originales Extraktionsfeld", "Für Vergleich verwendeter Wert", "Bewertung"], [[
            row.get("reference_value"), row.get("original_prediction_value", row.get("prediction_value")),
            row.get("prediction_value"), STATUSES[status]]])
        card += f'<p><strong>{esc(CERTAINTY[certainty])}: {esc(CATEGORIES[category])}</strong> · Stufe: {esc(finding["stage"])}<br>{esc(finding["reason"])}</p>'
        if row.get("name_swapped") and truth(row["name_swapped"]):
            card += '<p>Vor-/Nachnamensrollen wurden ausschließlich im Referenzvergleich vertauscht; Originalausgabe bleibt unverändert.</p>'
        if finding.get("provenance") == "docling_vlm_assist":
            orig_docling = finding.get("original_docling_value")
            card += (
                f'<p><strong>Herkunft:</strong> Docling + VLM-Hybridstufe '
                f'(Original-Docling: {esc(str(orig_docling if orig_docling is not None else "—"))})</p>'
            )
        elif finding.get("provenance") == "docling":
            card += '<p><strong>Herkunft:</strong> Docling (deterministisch)</p>'
        if finding["evidence"]:
            card += '<pre>' + esc(json.dumps(finding["evidence"], ensure_ascii=False, indent=2)) + '</pre>'
        if page:
            card += f'<p><a href="#page-{digest(key)[:16]}">OCR, Modellantwort und Seitenstufen öffnen</a></p>'
            crop_path = crop(source, output, page, finding.get("bbox"), [*key, row.get("output_index"), source_field(row), finding.get("bbox")])
            if crop_path:
                card += f'<details><summary>Extrahierter Quellbereich (keine unabhängige Referenzlokalisierung)</summary><img style="max-width:100%" src="{esc(crop_path)}" alt="Extrahierter Quellbereich"></details>'
        if finding["observations"]:
            card += '<details><summary>Original-OCR im Quellbereich</summary>' + table(
                ["Quellbeleg", "Unveränderter OCR-Text", "Engine-Score", "An Zuordnung übergeben", "Zuordnungsstatus"],
                [[o["id"], o["text"], o.get("confidence"), o.get("submitted_to_assignment"), o.get("reason")]
                 for o in finding["observations"]]) + '</details>'
        cards.append(card+'</article>')
        records.append(dict(row, analysis=finding))
    page_sections = []
    for key, page in pages.items():
        raw, ledger = raw_pages[key], ledgers[key]
        body = f'<section class="page-analysis box" id="page-{digest(key)[:16]}" data-method="{esc(key[0])}" data-page="{esc(page.document_id+":"+str(page.page_number))}">'
        body += f'<h2>{esc(key[0])} · {esc(names.get(page.document_id) or page.document_id[:12])} · PDF-Seite {page.page_number}</h2>'
        body += '<p>Erwartete Felder dieser Seite sind nur für zugeordnete Referenzpersonen bekannt. Ungepaarte Kursreferenzen stehen bei „Seite unbekannt“.</p>'
        body += f'<p>Extrahierte Personen: {len(page.participants)} · Status: {esc(page.status)} · Format: {esc(page.parse_status)}. '
        body += 'Reine OCR-Ausgaben werden nicht als Teilnehmerextraktion bewertet.</p>' if page.output_kind == 'ocr_text' else '</p>'
        if not raw:
            body += '<p>Keine gespeicherten OCR-/Modellrohbelege verfügbar. Daraus folgt kein Nachweis fehlender OCR-Erkennung.</p>'
        body += '<details><summary>Verarbeitungsstufen und belegte Ablehnungen</summary><pre>'+esc(json.dumps(
            {k: ledger.get(k) for k in ("capture_coverage", "counts", "row_selection", "rejected_model_rows", "field_warnings", "mapper_row_decisions", "mapping", "role_filter")},
            ensure_ascii=False, indent=2))+'</pre></details>'
        if raw.get("structure", {}).get("mapping_diagnostics"):
            body += '<p>Die gespeicherten Mappergründe belegen eine technische Zuordnungslücke. Ohne Referenzkoordinaten ist damit kein bestimmter fehlender Referenzwert lokalisiert.</p>'
        body += '<details><summary>Alle OCR-Rohbeobachtungen einschließlich niedriger/fehlender Scores</summary>' + table(
            ["Quellbeleg", "Originaltext", "Engine-Score", "Position", "An Zuordnung übergeben", "Zuordnung"],
            [[o["id"], o["text"], o.get("confidence"), json.dumps(o.get("bbox")), o.get("submitted_to_assignment"), o.get("reason")]
             for o in ledger["observations"]]) + '</details>'
        recognized = raw.get("structure", {})
        for number, native_table in enumerate(recognized.get("tables", []), 1):
            body += f'<details><summary>Unveränderte Tabellenzellen / Markup {number}</summary><pre>' + esc(
                json.dumps(native_table.get("native", {}).get("data", {}), ensure_ascii=False, indent=2) if native_table.get("native") else native_table.get("html", "")) + '</pre></details>'
        answers = [r.get("raw_response") for r in raw.get("responses", []) if r.get("raw_response")]
        if raw.get("assignment", {}).get("raw_response"):
            answers.append(raw["assignment"]["raw_response"])
        for answer in answers:
            body += '<details><summary>Unveränderte gespeicherte Modellantwort</summary><pre>'+esc(answer)+'</pre></details>'
        if paths[key]:
            body += f'<p><a href="{esc(relative_link(paths[key], output))}">Vollständige Rohdaten mit Eingaben, Zwischenständen und Belegen</a></p>'
        image = source / "pages" / (page.page_id+".png")
        if image.resolve().is_relative_to(source / "pages") and image.is_file():
            body += f'<details><summary>Seitenbild</summary><a href="{esc(relative_link(image, output))}"><img loading="lazy" width="700" style="max-width:100%" src="{esc(relative_link(image, output))}" alt="Originales Seitenbild"></a></details>'
        page_sections.append(body+'</section>')
    content = '<h1>Extraktionsfehleranalyse</h1><p><a href="report.html">Ergebnisbericht</a> · <a href="details.html">Berechnung und Zuordnung</a> · <a href="error_analysis/fields.json">Feldanalyse als JSON</a></p>'
    content += '<div class="box">Diese Seite erklärt gespeicherte Ergebnisse. Referenzen beeinflussen ausschließlich den Vergleich. Fehlende Felder bleiben im Nenner. '
    content += 'OCR-Score ist keine Wahrscheinlichkeit. Ein fehlender Referenztext im OCR-Volltext beweist weder einen Erkennungsfehler noch eine bestimmte Fehlerstufe. '
    content += 'Nachgewiesen bezeichnet einen gespeicherten Verarbeitungsschritt; Vermutung eine mögliche Erklärung; Unbekannt fehlende Belege. '
    content += 'Die Excel-Kursreferenz besitzt keine Seiten-/Zeilenkoordinaten. Keine künstliche Zuordnung fehlender Personen zur Handschriftseite.</div>'
    content += table(["Verfahren", "Korrekt", "Falsch", "Fehlend", "Zusätzlich", "Nicht bewertbar"],
        [[method, *(counts[method, status] for status in STATUSES)] for method in metrics["methods"]])
    if unavailable:
        content += '<p>Quellvorhersagen nicht verfügbar: '+esc(", ".join(unavailable))+'. Ursachen bleiben unbekannt.</p>'
    content += '<div class="filters">' + select("method", "Verfahren", [(m, m) for m in metrics["methods"]])
    content += select("page", "PDF-Seite", page_values) + select("field", "Feldtyp", [(f, f) for f in FIELDS])
    content += select("category", "Fehlerkategorie", CATEGORIES.items()) + select("certainty", "Beleglage", CERTAINTY.items())
    content += select("result", "Feldbewertung", STATUSES.items())
    content += '<label>Suche <input id="search" type="search"></label> · Sichtbare Feldfälle: <span id="visible-count"></span></div>'
    content += ''.join(cards) + '<h2>OCR und Stufen pro Verfahren/PDF-Seite</h2>' + ''.join(page_sections)
    path = output / "extraction_errors.html"
    path.write_text(document("Extraktionsfehleranalyse", content, script_source=SCRIPT), encoding="utf-8")
    write_json(folder / "fields.json", dict(version=VERSION, source_run=str(source), fields=records,
        limitations=["course_reference_has_no_page_coordinates", "reference_alignment_is_not_independent_identity_verification"]))
    write_json(folder / "checks.json", dict(version=VERSION, field_rows=len(fields), explained_field_rows=len(records),
        counts={m: {s: counts[m, s] for s in STATUSES} for m in metrics["methods"]},
        categories=[dict(category=c, certainty=s, count=n) for (c, s), n in categories.items()],
        implementation_sha256=file_hash(Path(__file__)), modified_scores=False, new_inference=False,
        raw_artifacts={relative_link(p, source): file_hash(p) for p in paths.values() if p}))
    for filename in ("report.html", "details.html"):
        target = output / filename
        if target.is_file():
            body = target.read_text(encoding="utf-8")
            if 'href="extraction_errors.html"' not in body:
                target.write_text(body.replace('</h1>', '</h1><p><a href="extraction_errors.html"><strong>Extraktionsfehleranalyse</strong></a></p>', 1), encoding="utf-8")
    return path
