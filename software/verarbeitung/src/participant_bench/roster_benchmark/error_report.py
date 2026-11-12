"""Local, evidence-limited loss analysis of frozen grading and extraction artifacts.

References enter only this presentation step. They never repair extraction or
locate unmatched course references on a guessed PDF page.
"""

import json
import os
from collections import Counter
from pathlib import Path

from ..column_context import mapping_reason
from ..config import METHODS
from ..io import digest, file_hash, read_json, read_jsonl, write_csv, write_json
from ..ocr_observations import audit
from ..schema import PageResult
from .detail_report import document, esc, read_csv, table, truth
from .matching import FIELDS
from .pipeline_trace import field_trace, page_trace

VERSION = "extraction-error-analysis-v6-input-budget"
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
const ids=['method','document','class','page','field','cause','category','certainty','stage','result'].filter(id=>document.getElementById(id));
const controls=ids.map(id=>document.getElementById(id));
const search=document.getElementById('search');
const apply=()=>{let count=0;
for(const card of document.querySelectorAll('article.field-case')){
const show=ids.every((id,i)=>!controls[i].value||card.dataset[id]===controls[i].value)&&
card.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
card.hidden=!show;if(show)count++;}
for(const section of document.querySelectorAll('section.page-analysis')){
const method=document.getElementById('method')?.value,page=document.getElementById('page')?.value;
const doc=document.getElementById('document')?.value;
section.hidden=!!((method&&section.dataset.method!==method)||(page&&section.dataset.page!==page)||
(doc&&section.dataset.document!==doc));}
document.getElementById('visible-count').textContent=String(count);};
if(typeof location!=='undefined'){
 const query=new URLSearchParams(location.search);
 for(const id of ids)if(query.has(id))document.getElementById(id).value=query.get(id);
}
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
        result["pipeline_trace"] = field_trace(row, page, raw, {}, [], field)
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
    if row_boxes and (not region or target.value is None):
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
        pipeline_trace=field_trace(row, page, raw, proof, related, field),
    )
    if status in ("correct", "unassessed", "extra"):
        reason = "Gespeicherter Feldvergleich; die Referenzpaarung ist keine unabhängige Identitätsprüfung."
        if name_swapped and row.get("field") in ("first_name", "last_name"):
            reason += " Vor-/Nachnamensrollen wurden für die Bewertung über Swap-Toleranz abgeglichen; dies bestätigt keine korrekten Extraktionsrollen."
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
    transition = result["pipeline_trace"]
    if status == "missing" and transition["loss_stage"] in ("column_mapping", "response_alignment"):
        result.update(category="column_mapping", certainty="proven", stage=transition["loss_stage"],
            reason="Die gespeicherte VLM-Antwort enthält physische Zellen, deren Zuordnung durch fehlende/mehrdeutige Überschriften oder ungleiche Zellzahlen blockiert wird. "
                   "Dies belegt den technischen Übergang, nicht die Richtigkeit einer bestimmten Zelle oder die Sichtbarkeit des Referenzwerts im Bild.")
        return result
    if status == "missing" and transition["loss_stage"] in ("literal_validation", "position_validation"):
        result.update(category="validation", certainty="proven", stage=transition["loss_stage"],
            reason="Ein verknüpfter Modellvorschlag ist vor dieser gespeicherten Validierungsstufe vorhanden und danach leer. Die Ablehnung beweist nicht die Richtigkeit des Vorschlags.")
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
            result.update(category="model_omission", certainty="proven", stage="assignment_or_postprocessing",
                reason="Der wörtliche Referenztext wurde aus diesem Quellbereich übergeben; im finalen Feld steht kein Wert. "
                       "Belegt ist der Übergabe-/Ausgabeunterschied. Modellinterne Auslassung und spätere Nachverarbeitung sind ohne Zwischenbelege nicht trennbar.")
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


CAUSES = {
    "recognition_or_assignment": "OCR-/Texterkennung oder Zuordnung (Hypothese)",
    "table_or_row": "Tabellen-/Zeilenbeobachtung ohne Zuordnung",
    "field_assignment": "Spalten-/Feld-/Namensrollenzuordnung",
    "input_selection": "Beleg nicht an Zuordnung übergeben",
    "assignment_or_postprocessing": "Feld fehlt zwischen Übergabe und finaler Ausgabe",
    "validation": "Validierungs-/Nachverarbeitungsschritt",
    "extra_output": "Zusätzliche Werte gegenüber Referenz; Halluzination nicht bewiesen",
    "unknown": "Ursache nicht eindeutig bestimmbar",
}


CAUSE_CATEGORY = dict(name_swap="field_assignment", column_mapping="field_assignment", validation="validation",
                   not_submitted="input_selection", model_omission="assignment_or_postprocessing",
                   ocr_suspected="recognition_or_assignment", extra="extra_output")


def aggregate_findings(records):
    counts = Counter()
    for record in records:
        finding = record["analysis"]
        if finding["result"] not in ("incorrect", "missing", "extra"):
            continue
        cause = CAUSE_CATEGORY.get(finding["category"], "unknown")
        counts[record["method"], record.get("document_id") or "unknown",record.get("class_id") or "unknown", record["field"], cause,
               finding["stage"], finding["certainty"], finding["result"]] += 1
    totals=Counter()
    for key,n in counts.items():
        totals[key[0]]+=n
    return [dict(zip(("method","document_id","class_id","field","cause","stage","certainty","result"),key,strict=True),count=n,
                 method_error_total=totals[key[0]],share_of_method_errors=n/totals[key[0]])
            for key,n in sorted(counts.items())]


def page_events(page, raw, ledger):
    """Saved page transitions are not localized GT errors; keep them separate from field-error totals."""
    events=[]
    def add(kind,stage,count):
        events.append(dict(method=page.method_id,document_id=page.document_id,page_number=page.page_number,
                           event=kind,stage=stage,count=count,certainty="proven",correctness_of_discarded_value="unknown"))
    if page.status in ("failed","unavailable"):
        add(page.status,"extraction",1)
    assignment = raw.get("assignment", {})
    input_failed = (assignment.get("error_stage") == "input_budget" or
                    not assignment.get("raw_response") and
                    assignment.get("error", "").startswith("ValueError: Input budget exceeded ("))
    if input_failed:
        add("input_budget_exceeded", "model_input", 1)
    elif page.parse_status == "invalid":
        add("invalid_structured_response","response_parsing",1)
    if any(r.get("output_budget_reached") for r in raw.get("responses", [])):
        add("output_budget_reached", "model_response", 1)
    for key in ("rejected_model_rows","field_warnings"):
        values=ledger.get(key)
        if isinstance(values,(list,dict)) and values:
            add(key,"validation",len(values))
    decisions=raw.get("structure",{}).get("row_decisions",[])
    unmatched=sum(r.get("status")=="unassigned" for r in decisions)
    if unmatched:
        add("unassigned_observed_rows","native_mapper",unmatched)
    answers=[r for r in raw.get("responses",[]) if r.get("parse_status")=="valid"]
    if raw.get("assignment",{}).get("raw_response"):
        answers.append(raw["assignment"])
    for response in answers:
        try:
            parsed=json.loads(response.get("raw_response", ""))
        except (ValueError,TypeError):
            continue
        values=parsed.get("participants",parsed.get("rows")) if isinstance(parsed,dict) else None
        if isinstance(values,list) and not values:
            add("empty_structured_response","model_response",1)
    if page.excluded_instructors:
        add("explicit_instructor_exclusion","role_filter",len(page.excluded_instructors))
    return events


def render_errors(output: Path, *, source_run: Path | None = None) -> Path:
    """Render saved scores and evidence. No extraction, reference reload or scoring."""
    output = output.resolve()
    identity, metrics = read_json(output / "identity.json"), read_json(output / "metrics.json")
    source = Path(source_run or identity["source_run"]).resolve()
    fields = read_csv(output / "fields.csv")
    grading_path=output/"scientific/error_grading.json"
    grading=read_json(grading_path) if grading_path.is_file() else {}
    specs=grading.get("sources") or {m:dict(source=str(source),method=m,
        extraction_sha256=identity.get("extraction_sha256",{}).get(m)) for m in metrics["methods"]}
    if grading:
        fields=grading["fields"]
        metrics=dict(metrics,methods={m:dict(status="scientific_grading") for m in specs})
    from ..output_order import document_order, ordered_rows

    manifest = read_json(source / "manifest.json") if (source / "manifest.json").is_file() else {}
    fields = ordered_rows(fields, document_order(manifest), {m: i for i, m in enumerate(metrics["methods"])})
    pages, raw_pages, ledgers, paths, pipeline_pages = {}, {}, {}, {}, {}
    source_metadata = {}
    unavailable = []
    folder = output / "error_analysis"
    folder.mkdir(exist_ok=True)
    for method in metrics["methods"]:
        actual_method=specs[method]["method"]
        current_source=Path(specs[method]["source"]).resolve()
        if actual_method not in {*METHODS, "ocr_rules"}:
            raise ValueError("Unbekanntes Verfahren im gespeicherten Vergleich")
        extraction = current_source / actual_method / "extractions.jsonl"
        if not extraction.is_file():
            unavailable.append(method)
            continue
        expected_hash = specs[method].get("extraction_sha256")
        if expected_hash is not None and file_hash(extraction) != expected_hash:
            raise ValueError("Quellvorhersagen wurden seit dem gespeicherten Vergleich verändert")
        if expected_hash is None and metrics["methods"][method].get("status") != "not_applicable":
            unavailable.append(method)
            continue
        for record in read_jsonl(extraction):
            page = PageResult.model_validate(record)
            if grading and page.document_id not in grading["document_ids"]:
                continue
            page=page.model_copy(update=dict(method_id=method))
            key = method, page.document_id, str(page.page_number)
            pages[key] = page
            raw_path = (current_source / actual_method / ("raw-"+page.page_id+".json")).resolve()
            if not raw_path.is_relative_to(current_source / actual_method):
                raise ValueError("Ungültiger lokaler Rohdatenpfad")
            raw = read_json(raw_path) if raw_path.is_file() else {}
            raw_pages[key], ledgers[key] = raw, audit(raw, page)
            if current_source not in source_metadata:
                source_metadata[current_source] = (
                    read_json(current_source / "manifest.json") if (current_source / "manifest.json").is_file() else {},
                    read_json(current_source / "effective_pages.json") if (current_source / "effective_pages.json").is_file() else [],
                )
            pipeline_pages[key] = page_trace(current_source, page, raw, *source_metadata[current_source])
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
            dict(method=row["method"], document=row.get("document_id") or "unknown", page=page_id,
                 field=row["field"],cause=CAUSE_CATEGORY.get(category,"unknown"), category=category, certainty=certainty,
                 stage=finding["stage"], result=status,**{"class":row.get("class_id") or "unknown"}).items()) +
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
        trace = finding.get("pipeline_trace", {})
        if trace:
            card += '<details><summary>Feldkette: OCR → Modellinput → Antwort → Validierung → Ausgabe</summary>'
            card += '<p>Die erste belegte Ausgabelücke ist keine automatisch bewiesene ursprüngliche Fehlerursache. Nicht lokalisierte oder fehlende Zwischenstände bleiben offen.</p>'
            card += table(["Stufe", "Gespeicherter Befund", "Wert / Zellen", "Weitere Belege"], [
                [s["stage"], s["status"], json.dumps(s.get("value"), ensure_ascii=False),
                 json.dumps({k:v for k,v in s.items() if k not in ("stage", "status", "value")}, ensure_ascii=False)]
                for s in trace["stages"]]) + '</details>'
        if page:
            card += f'<p><a href="#page-{digest(key)[:16]}">OCR, Modellantwort und Seitenstufen öffnen</a></p>'
            crop_path = crop(Path(specs[row["method"]]["source"]), output, page, finding.get("bbox"), [*key, row.get("output_index"), source_field(row), finding.get("bbox")])
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
        body = f'<section class="page-analysis box" id="page-{digest(key)[:16]}" data-method="{esc(key[0])}" data-document="{esc(page.document_id)}" data-page="{esc(page.document_id+":"+str(page.page_number))}">'
        body += f'<h2>{esc(key[0])} · {esc(names.get(page.document_id) or page.document_id[:12])} · PDF-Seite {page.page_number}</h2>'
        body += '<p>Erwartete Felder dieser Seite sind nur für zugeordnete Referenzpersonen bekannt. Ungepaarte Kursreferenzen stehen bei „Seite unbekannt“.</p>'
        chain = pipeline_pages[key]
        body += '<details><summary>Original-PDF → Ausrichtung → tatsächliches Laufbild → Spaltenkontext</summary>'
        if chain.get("review_required") and not chain.get("curation_reviewed"):
            body += '<p class="bad"><strong>Ausrichtung prüfpflichtig.</strong> Ein gespeicherter Drehwinkel von 0° bestätigt keine korrekte Ausrichtung. Unsichere OSD-Ergebnisse werden nicht automatisch übernommen.</p>'
        body += '<pre>' + esc(json.dumps(chain, ensure_ascii=False, indent=2)) + '</pre>'
        original = chain.get("source_path")
        if original and Path(original).is_file():
            body += f'<p><a href="{esc(relative_link(original, output))}">Original-PDF öffnen (Seite {page.page_number})</a></p>'
        body += '</details>'
        body += '<h3>Seitenübergreifende Spaltenzuordnung</h3>'
        body += '<p>Nur die Spaltenstruktur darf übernommen werden; sämtliche Feldwerte stammen aus der aktuellen Seite. '
        body += 'Spaltenindizes beginnen bei 0, X-Positionen sind auf die Seitenbreite normiert. '
        body += 'Neue eindeutige Überschriften haben Vorrang; fehlende historische Angaben bleiben unbekannt.</p>'
        body += table(['Überschriften von Seite', 'Entscheidung', 'Feld → Spaltenindex', 'Überschriftenbelege',
                       'Begründung', 'Gemessener Geometrievergleich'],
            [[t.get('source_page'), t.get('status'), t.get('column_mapping', t.get('columns')),
              t.get('headings'), mapping_reason(t), t.get('geometry_check')]
             for t in chain.get('column_mappings', [])])
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
        requests = [r for r in [*raw.get("responses", []), raw.get("assignment", {})] if r.get("text_prompt")]
        for request in requests:
            body += '<details><summary>Tatsächlich gespeicherter Modellinput und Prompthashes</summary><pre>' + esc(json.dumps(
                {k:request.get(k) for k in ("prompt_version", "system_prompt_sha256", "text_prompt_sha256", "generation_schema_sha256", "text_prompt")},
                ensure_ascii=False, indent=2)) + '</pre></details>'
        stages = {k:v for k,v in raw.get("assignment", {}).items() if k.startswith("participants_") or k == "observed_cell_completions"}
        if stages:
            body += '<details><summary>Gespeicherte Teilnehmer vor und nach den Validierungen</summary><pre>' + esc(json.dumps(stages, ensure_ascii=False, indent=2)) + '</pre></details>'
        if raw.get("assignment", {}).get("raw_response"):
            answers.append(raw["assignment"]["raw_response"])
        for answer in answers:
            body += '<details><summary>Unveränderte gespeicherte Modellantwort</summary><pre>'+esc(answer)+'</pre></details>'
        if paths[key]:
            body += f'<p><a href="{esc(relative_link(paths[key], output))}">Vollständige Rohdaten mit Eingaben, Zwischenständen und Belegen</a></p>'
        page_source=Path(specs[key[0]]["source"])
        image = page_source / "pages" / (page.page_id+".png")
        if image.resolve().is_relative_to(page_source / "pages") and image.is_file():
            body += f'<details><summary>Seitenbild</summary><a href="{esc(relative_link(image, output))}"><img loading="lazy" width="700" style="max-width:100%" src="{esc(relative_link(image, output))}" alt="Originales Seitenbild"></a></details>'
        page_sections.append(body+'</section>')
    content = '<h1>Extraktionsfehleranalyse</h1><p><a href="report.html">Ergebnisbericht</a> · <a href="details.html">Berechnung und Zuordnung</a> · <a href="error_analysis/fields.json">Feldanalyse als JSON</a> · <a href="error_analysis/page_pipeline.json">Seitenkette als JSON</a></p>'
    content+='<p><strong>Bewertung:</strong> '+esc(grading.get("label","Gespeicherter Standard-Bewertungsmodus"))+'.</p>'
    content += '<div class="box">Diese Seite erklärt gespeicherte Ergebnisse. Referenzen beeinflussen ausschließlich den Vergleich. Fehlende Felder bleiben im Nenner. '
    content += 'OCR-Score ist keine Wahrscheinlichkeit. Ein fehlender Referenztext im OCR-Volltext beweist weder einen Erkennungsfehler noch eine bestimmte Fehlerstufe. '
    content += 'Nachgewiesen bezeichnet einen gespeicherten Verarbeitungsschritt; Vermutung eine mögliche Erklärung; Unbekannt fehlende Belege. '
    content += 'Die Excel-Kursreferenz besitzt keine Seiten-/Zeilenkoordinaten. Keine künstliche Zuordnung fehlender Personen zur Handschriftseite.</div>'
    content += table(["Verfahren", "Korrekt", "Falsch", "Fehlend", "Zusätzlich", "Nicht bewertbar"],
        [[method, *(counts[method, status] for status in STATUSES)] for method in metrics["methods"]])
    unique_pages = {(k[1], k[2], v.get("image_sha256")):v for k,v in pipeline_pages.items()}
    content += '<details><summary>PDF-Ausrichtung und Laufbilder je Seite</summary>'
    content += '<p>Diese Messwerte bestätigen die verarbeitete Datei, nicht deren visuell richtige Ausrichtung. Fehlende historische OSD-Vorschläge bleiben unbekannt.</p>'
    content += table(["Dokument", "Seite", "Entscheidung / Methode", "OSD-Konfidenz / Schwelle", "OSD-Vorschlag / übernommen / manuell (°)"], [
        [d[:12], p, f"{v['orientation_status']} / {v['orientation_method']}", f"{v['orientation_confidence']} / {v['orientation_min_confidence']}",
         f"{v['orientation_proposed_clockwise']} / {v['additional_rotation_clockwise']} / {v['curation_rotation_clockwise']}"]
        for (d,p,_),v in unique_pages.items()]) + '</details>'
    aggregated=aggregate_findings(records)
    events=[event for key,page in pages.items() for event in page_events(page,raw_pages[key],ledgers[key])]
    totals=Counter()
    for row in aggregated:
        totals[row["method"],row["cause"],row["stage"],row["certainty"]]+=row["count"]
    content+='<h2>Aggregierte Fehler und gespeicherte Stufenereignisse</h2>'
    content+=table(["Verfahren","Fehlerbereich","Stufe","Beleglage","Feldfälle"],
        [[m,CAUSES[c],stage,CERTAINTY[certainty],n] for (m,c,stage,certainty),n in sorted(totals.items())])
    content+='<p>Aggregiert werden ausschließlich falsche, fehlende und zusätzliche Felder des gespeicherten Bewertungsmodus. '
    content+='Nachgewiesen bezeichnet den beobachteten Übergang, nicht automatisch die ursprüngliche Fehlerursache. '
    content+='Zusätzliche Referenzabweichung beweist keine visuelle Halluzination. OCR-/Tabellenlesefehler sind ohne '
    content+='unabhängige Referenzlokalisierung häufig nicht trennbar. Null beobachtete Ereignisse beweisen keine Fehlerfreiheit.</p>'
    content+=table(["Verfahren","Dokument","Seite","Gespeichertes Ereignis","Stufe","Anzahl"],
        [[r[k] for k in ("method","document_id","page_number","event","stage","count")] for r in events])
    write_json(folder / "page_pipeline.json", [dict(method=k[0], document_id=k[1], **v) for k,v in pipeline_pages.items()])
    content+='<p>Seitenereignisse werden separat gezählt und nicht zu den Feldfehlern addiert. Eine leere Modellantwort '
    content+='ist ein gespeicherter Befund, ohne lokalisierte Soll-Zeilen aber kein Nachweis einer bestimmten ausgelassenen Person. '
    content+='<a href="error_analysis/summary.csv">Aggregierte Feldfehler CSV</a> · '
    content+='<a href="error_analysis/page_events.csv">Seitenereignisse CSV</a></p>'
    if unavailable:
        content += '<p>Quellvorhersagen nicht verfügbar: '+esc(", ".join(unavailable))+'. Ursachen bleiben unbekannt.</p>'
    content += '<div class="filters">' + select("method", "Verfahren", [(m, m) for m in metrics["methods"]])
    doc_values=sorted({r.get("document_id") or "unknown" for r in fields})
    content += select("document","Dokument",[(d,names.get(d,d)) for d in doc_values])
    content += select("class","Schulung",[(c,c) for c in sorted({r.get("class_id") or "unknown" for r in fields})])
    content += select("cause","Fehlerbereich",CAUSES.items())
    content += select("page", "PDF-Seite", page_values) + select("field", "Feldtyp", [(f, f) for f in FIELDS])
    content += select("category", "Fehlerkategorie", CATEGORIES.items()) + select("certainty", "Beleglage", CERTAINTY.items())
    content += select("result", "Feldbewertung", STATUSES.items())
    content += select("stage", "Verarbeitungsstufe", [(s,s) for s in sorted({r["analysis"]["stage"] for r in records})])
    content += '<label>Suche <input id="search" type="search"></label> · Sichtbare Feldfälle: <span id="visible-count"></span></div>'
    content += ''.join(cards) + '<h2>OCR und Stufen pro Verfahren/PDF-Seite</h2>' + ''.join(page_sections)
    path = output / "extraction_errors.html"
    path.write_text(document("Extraktionsfehleranalyse", content, script_source=SCRIPT), encoding="utf-8")
    write_json(folder / "fields.json", dict(version=VERSION, source_run=str(source), fields=records,
        limitations=["course_reference_has_no_page_coordinates", "reference_alignment_is_not_independent_identity_verification"]))
    write_json(folder/"summary.json",dict(version=VERSION,fields=aggregated,page_events=events,causes=CAUSES,
                                        grading_label=grading.get("label","saved_standard"),
                                        field_error_total=sum(r["count"] for r in aggregated),page_events_are_separate=True))
    write_csv(folder/"summary.csv",aggregated,fields=None if aggregated else ["method","document_id","field","cause","stage","certainty","result","count"])
    write_csv(folder/"page_events.csv",events,fields=None if events else ["method","document_id","page_number","event","stage","count"])
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
