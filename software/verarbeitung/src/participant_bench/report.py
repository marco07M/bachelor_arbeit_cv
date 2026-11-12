import html
import json
import re
from pathlib import Path

from .column_context import mapping_diagnostics, mapping_reason
from .evaluation import DEFINITIONS
from .excel_columns import field_labels, write_participants_xlsx
from .io import digest, read_json, read_jsonl, write_csv, write_json, write_jsonl
from .ocr import raw_transcript
from .ocr_layout import model_input, readable_text
from .ocr_observations import export as observation_export
from .schema import TEXT_FIELDS, PageResult


def cost_scenario(config):
    assumptions = config.costs.model_dump()
    result = {
        "assumptions": assumptions,
        "note": "Zeitwert ist keine nachgewiesene Zahlungsersparnis; "
        "kein produktiver Import implementiert. Entwicklung getrennt von laufenden Kosten.",
    }
    c = config.costs
    required = (
        c.volume,
        c.hourly_rate_eur,
        c.manual_minutes_per_page,
        c.review_minutes_per_page,
        c.local_operating_eur_per_page,
    )
    if any(v is None for v in required):
        result["status"] = "not_calculated_missing_process_data"
        return result
    energy = None
    if c.energy_kwh_per_page is not None and c.electricity_eur_per_kwh is not None:
        energy = c.energy_kwh_per_page * c.electricity_eur_per_kwh * c.volume
    result.update(
        status=c.kind,
        manual_time_value_eur=c.volume * c.manual_minutes_per_page / 60 * c.hourly_rate_eur,
        review_time_value_eur=c.volume * c.review_minutes_per_page / 60 * c.hourly_rate_eur,
        freed_hours=c.volume * (c.manual_minutes_per_page - c.review_minutes_per_page) / 60,
        local_operating_eur=c.volume * c.local_operating_eur_per_page,
        energy_eur=energy,
        development_time_value_eur=c.development_hours * c.hourly_rate_eur
        if c.development_hours is not None
        else None,
    )
    return result


def report(output, summary, results, metrics, manifest, costs, *, columns=None):
    from .output_order import document_order, page_key
    from .roster_benchmark.evaluation import identify_course

    rows, excluded_instructors, name_orders, column_mappings = [], [], [], []
    labels = field_labels(columns)
    excel_groups = {}
    page_outputs, text_records, overview, ocr_records, signature_records = [], [], [], [], []
    observation_views = []
    sources = {page["page_id"]: page for page in manifest["pages"]}
    documents_in_order = document_order(manifest)
    for method, pages in results.items():
        excel_groups[method] = []
        truncated_pages = 0
        has_assignment = False
        for page in sorted(pages, key=lambda p: page_key(p, documents_in_order)):
            raw_path = output / method / f"raw-{page.page_id}.json"
            raw = read_json(raw_path) if raw_path.is_file() else {}
            if "ocr" in raw or "structure" in raw:
                observation_views.append(observation_export(output, method, page, raw))
            for trace in mapping_diagnostics(raw):
                column_mappings.append(dict(method=method, document_id=page.document_id, page_number=page.page_number,
                    table=trace.get("table_index"), source_page=trace.get("source_page"), status=trace.get("status", "not_recorded"),
                    reason=trace.get("reason"), explanation=mapping_reason(trace),
                    column_mapping=trace.get("column_mapping", trace.get("columns")),
                    headings=trace.get("headings"), geometry=trace.get("geometry"), geometry_check=trace.get("geometry_check")))
            has_assignment = has_assignment or "assignment" in raw
            responses = raw.get("responses", [])
            truncated = any(response.get("output_budget_reached") for response in responses)
            truncated_pages += truncated
            error = page.error or " | ".join(r["error"] for r in responses if r.get("error"))
            if truncated:
                error = "Modellantwort am Ausgabelimit abgeschnitten. Die Rohantwort ist unten verlinkt."
            source_name = Path(sources.get(page.page_id, {}).get("source_path", page.document_id)).name
            if "document_name_order" in raw:
                audit = raw["document_name_order"]
                decision = audit.get("decision") or {}
                name_orders.append(dict(method=method, source_file=source_name, document_id=page.document_id,
                    page_number=page.page_number, origin_page=audit.get("origin_page"),
                    name_order=decision.get("order", "unknown"), evidence=decision.get("evidence") or
                        " | ".join(item["evidence"] for item in audit.get("reported_decisions", [])),
                    decision_source=audit.get("decision_source", "model"),
                    split_rows=sum(row["action"] == "split" or row.get("previously_split", False) or row.get("prevalidation_split", False)
                                   for row in audit["actions"]),
                    swapped_rows=sum(row["action"] == "swap" or row.get("previously_swapped", False) or row.get("prevalidation_swap", False)
                                     for row in audit["actions"]),
                    review_rows=sum(row["action"] == "review" for row in audit["actions"]),
                    conflict=audit["conflicting_page_decision"]))
            for person in page.excluded_instructors:
                excluded_instructors.append(dict(method=method, source_file=source_name, page_number=page.page_number,
                    first_name=person.first_name.value, last_name=person.last_name.value,
                    role_evidence=person.role_evidence, reason="Explizit als Kursleiter/Trainer gekennzeichnet"))
            class_id = identify_course(source_name, set())
            if not re.fullmatch(r"[0-9]{6}", class_id):
                class_id = None
            for check in raw.get("signature_checks", []):
                relative = Path(check["crop"]) if check.get("crop") else None
                crop = (Path(method) / relative).as_posix() if relative and not relative.is_absolute() and ".." not in relative.parts else None
                signature_records.append({
                    "method": method, "page_id": page.page_id, "source_file": source_name,
                    "page_number": page.page_number, "output_index": check["output_index"],
                    "signature_present": check.get("signature_present"),
                    "prior_signature_present": check.get("prior_signature_present"),
                    "detail_signature_present": check.get("observation", {}).get("signature_present"),
                    "location_source": check.get("location_source"),
                    "evidence": check.get("observation", {}).get("evidence"),
                    "field_located": check.get("observation", {}).get("field_located"),
                    "cache_hit": check.get("cache_hit", False), "error": check.get("error"), "crop": crop,
                })
            fallback = page.output_kind != "ocr_text" and (page.text_fallback or (not page.participants and page.page_text is not None))
            record = {
                "method": method, "document_id": page.document_id, "page_id": page.page_id,
                "source_file": source_name, "page_number": page.page_number, "status": page.status,
                "response_format": page.parse_status, "participants": len(page.participants),
                "excluded_instructors": len(page.excluded_instructors),
                "output_kind": page.output_kind,
                "output_budget_reached": truncated, "error": error or None,
                "text_fallback": fallback, "page_text": page.page_text if fallback else None,
                "review_notes": " | ".join(page.review_notes),
            }
            text_records.append(record)
            links = []
            if "structure" in raw:
                recognized = raw["structure"]
                for key, suffix, title in (("markdown", "md", "Strukturierter Seitentext"),
                                           ("plain_text", "txt", "Vollständiger Klartext")):
                    relative = Path(method) / "ocr_text" / f"{page.page_id}.{suffix}"
                    (output / relative).parent.mkdir(parents=True, exist_ok=True)
                    (output / relative).write_text(recognized[key], encoding="utf-8", newline="")
                    links.append((relative.as_posix(), title))
                # Store HTML as inert text; never render untrusted model markup in the report.
                for index, table in enumerate(recognized["tables"]):
                    relative = Path(method) / "tables" / f"{page.page_id}-t{index + 1}.html.txt"
                    (output / relative).parent.mkdir(parents=True, exist_ok=True)
                    (output / relative).write_text(table["html"], encoding="utf-8", newline="")
                    links.append((relative.as_posix(), f"Tabelle {index + 1}: Zellstruktur als HTML-Text"))
                links.append(((Path(method) / raw_path.name).as_posix(), "Native Layout-, Tabellen- und Zellbelege"))
                ocr_records.append(dict(method=method, page_id=page.page_id, source_file=source_name,
                    page_number=page.page_number, text=recognized["plain_text"], word_count=None, links=list(links)))
            if "unlimited_ocr" in raw:
                recognized = raw["unlimited_ocr"]
                plain_path = Path(method) / "ocr_text" / f"{page.page_id}.txt"
                (output / plain_path).parent.mkdir(parents=True, exist_ok=True)
                (output / plain_path).write_text(recognized["clean_text"], encoding="utf-8", newline="")
                native_links = [(plain_path.as_posix(), "Vollständiger OCR-Text mit Tabellenstruktur"),
                                ((Path(method) / raw_path.name).as_posix(), "Rohantwort, Layoutregionen und Zellzuordnung")]
                if "assignment" in raw:
                    assigned = raw["assignment"]
                    for key, title in (("text_prompt", "Exakte LLM-Eingabe zur Zellzuordnung"),
                                       ("raw_response", "LLM-Antwort zur Zellzuordnung")):
                        if key in assigned:
                            relative = Path(method) / "assignment" / f"{page.page_id}-{key}.txt"
                            (output / relative).parent.mkdir(parents=True, exist_ok=True)
                            (output / relative).write_text(assigned[key], encoding="utf-8", newline="")
                            native_links.append((relative.as_posix(), title))
                ocr_records.append(dict(method=method, page_id=page.page_id, source_file=source_name,
                    page_number=page.page_number, text=recognized["clean_text"], word_count=None,
                    links=native_links))
                links.extend(native_links)
            if "ocr" in raw:
                links.append(((Path(method) / raw_path.name).as_posix(), "OCR-Rohdaten mit Wortpositionen"))
                plain = raw_transcript(raw["ocr"]) if method == "ocr_raw" else readable_text(raw["ocr"])
                plain_path = Path(method) / "ocr_text" / f"{page.page_id}.txt"
                (output / plain_path).parent.mkdir(parents=True, exist_ok=True)
                (output / plain_path).write_text(plain, encoding="utf-8", newline="")
                links.append((plain_path.as_posix(), "OCR-Klartext als TXT"))
                word_path = Path(method) / "ocr_words" / f"{page.page_id}.csv"
                write_csv(output / word_path, [
                    {"word_id": index, "text": word["text"], **word["bbox"],
                     "ocr_confidence": word["ocr_confidence"]}
                    for index, word in enumerate(raw["ocr"]["words"])
                ])
                ocr_links = [(plain_path.as_posix(), "OCR-Klartext als TXT"),
                             (word_path.as_posix(), "OCR-Wörter mit IDs als CSV")]
                if method == "ocr_llm":
                    for index, response in enumerate(responses):
                        prompt = response.get("text_prompt") or model_input(raw["ocr"])
                        if digest(prompt) != response.get("text_prompt_sha256"):
                            continue  # Older input formats must not be presented as an exact model prompt.
                        prompt_path = Path(method) / "model_input" / f"{page.page_id}-{index + 1}.txt"
                        (output / prompt_path).parent.mkdir(parents=True, exist_ok=True)
                        (output / prompt_path).write_text(prompt, encoding="utf-8", newline="")
                        ocr_links.append((prompt_path.as_posix(), f"Exakte LLM-Eingabe ({index + 1})"))
                ocr_records.append({"method": method, "page_id": page.page_id,
                                    "source_file": source_name, "page_number": page.page_number,
                                    "text": plain, "word_count": len(raw["ocr"]["words"]),
                                    "links": ocr_links})
            if fallback and page.page_text is not None:
                text_path = Path(method) / "texts" / f"{page.page_id}.txt"
                (output / text_path).parent.mkdir(parents=True, exist_ok=True)
                (output / text_path).write_text(page.page_text, encoding="utf-8", newline="")
                links.append((text_path.as_posix(), "Seitentext als TXT"))
            raw_texts = [r["raw_response"] for r in responses if "raw_response" in r]
            if raw_texts:
                raw_text_path = Path(method) / "raw_text" / f"{page.page_id}.txt"
                (output / raw_text_path).parent.mkdir(parents=True, exist_ok=True)
                (output / raw_text_path).write_text("\n\n".join(raw_texts), encoding="utf-8", newline="")
                links.append((raw_text_path.as_posix(), "Unveränderte Modellantwort"))
            page_outputs.append((record, links))
            for i, participant in enumerate(page.participants):
                excel_groups[method].append(dict(
                    class_id=class_id, user_id=participant.personnel_number.value,
                    first_name=participant.first_name.value, last_name=participant.last_name.value,
                    short_code=participant.department.value, source_file=source_name,
                    document_id=page.document_id, page_number=page.page_number, output_index=i))
                rows.append(
                    {
                        "method": method,
                        "document_id": page.document_id,
                        "class_id": class_id,
                        "page_number": page.page_number,
                        "output_index": i,
                        "row_ref": participant.row_ref,
                        **{name: getattr(participant, name).value for name in TEXT_FIELDS},
                        **{name + "_state": getattr(participant, name).state for name in TEXT_FIELDS},
                        "signature_present": participant.signature_present,
                        "signature_state": participant.signature_state,
                        "signature_method": participant.signature_method,
                        "review_notes": " | ".join(participant.review_notes),
                    }
                )
        overview.append({
            "Verfahren": method, "Seiten zur Extraktion": len(pages),
            "Ausgabeart": summary[method].get("output_kind", "structured"),
            "Modell-Backend": summary[method].get("model_backend", "historischer Lauf"),
            "Modelle (konfiguriert)": " + ".join(str(value) for value in summary[method].get(
                "models_required", summary[method].get("models_used", [])) if value) or "—",
            "Feld-/Tabellenzuordnung": ("lokales LLM" if has_assignment else
                                    "deterministisches Spaltenmapping + VLM-Hybridstufe" if summary[method].get("assignment_backend") == "deterministic_headers_vlm_assist" else
                                    "deterministisches Spaltenmapping" if summary[method].get("assignment_backend") == "deterministic_headers" else
                                    "Bild und Paddle-OCR im VLM" if method == "ocr_vlm" else
                                    "PP-StructureV3" if method == "paddle_structure" else
                                    "TableFormer" if method == "docling" else
                                    "keine (Rohtext)" if method == "ocr_raw" else
                                    "Tabellenparser/OCR" if method == "unlimited_ocr" else "—"),
            "Antworten mit gültigem Format": sum(p.parse_status == "valid" for p in pages),
            "Teilnehmende": sum(len(p.participants) for p in pages),
            "Ausgeschlossene Kursleiter/Trainer": sum(len(p.excluded_instructors) for p in pages),
            "Unterschrift vorhanden": sum(person.signature_present is True for p in pages for person in p.participants),
            "Unterschriftsfeld leer": sum(person.signature_present is False for p in pages for person in p.participants),
            "Unterschrift unklar": sum(person.signature_present is None for p in pages for person in p.participants),
            "Unklare Detailprüfungen": sum(row["detail_signature_present"] is None for row in signature_records if row["method"] == method),
            "Signaturverfahren": summary[method].get("signature_backend", "historischer Lauf"),
            "Signaturquelle": " | ".join(sorted({person.signature_method or "unbekannt" for page in pages for person in page.participants})),
            "Seiten mit Text-Fallback": sum(r[0]["text_fallback"] for r in page_outputs if r[0]["method"] == method),
            "Abgeschnittene Modellantworten": truncated_pages,
            "Extraktionsfehler": sum(p.status in ("failed", "unavailable") for p in pages),
            "Status": summary[method]["status"],
        })
    write_jsonl(output / "page_text.jsonl", text_records)
    write_jsonl(output / "ocr_text.jsonl", ocr_records)
    write_csv(output / "pages.csv", [{k: v for k, v in row.items() if k != "page_text"} for row in text_records])
    write_csv(output / "extractions.csv", rows)
    write_csv(output / "document_column_mappings.csv", column_mappings,
              fields=["method", "document_id", "page_number", "table", "source_page", "status", "reason", "explanation",
                      "column_mapping", "headings", "geometry", "geometry_check"])
    write_csv(output / "document_name_orders.csv", name_orders, fields=["method", "source_file", "document_id",
        "page_number", "origin_page", "name_order", "evidence", "decision_source", "split_rows", "swapped_rows", "review_rows", "conflict"])
    write_csv(output / "excluded_instructors.csv", excluded_instructors, fields=[
        "method", "source_file", "page_number", "first_name", "last_name", "role_evidence", "reason"])
    write_participants_xlsx(output / "participants.xlsx", excel_groups, columns)
    write_json(output / "column_names.json", columns or {key: labels[key] for key in
               ("class_id", "user_id", "first_name", "last_name", "short_code")})
    if signature_records:
        write_csv(output / "signature_checks.csv", signature_records)
    write_csv(output / "methods.csv", [dict(method=method, **values) for method, values in summary.items()])
    write_json(output / "metrics.json", metrics)
    quality_rows = []
    for method, scores in metrics.items():
        aggregate = scores["aggregate"]
        for field, values in aggregate["fields"].items():
            quality_rows.append(
                {
                    "method": method,
                    "field": field,
                    "exact_correct": values["exact_match"]["numerator"],
                    "exact_total": values["exact_match"]["denominator"],
                    "exact_match": values["exact_match"]["value"],
                    "raw_exact_match": values.get("raw_exact_match", {}).get("value"),
                    "cer_edits": values["cer"]["numerator"],
                    "cer_characters": values["cer"]["denominator"],
                    "cer": values["cer"]["value"],
                    **{key: values["prf"][key] for key in ("tp", "fp", "fn")},
                    **{key: values["prf"][key]["value"] for key in ("precision", "recall", "f1")},
                    "unknown_count": values["unknown_rate"]["numerator"],
                    "coverage_denominator": values["coverage"]["denominator"],
                    "coverage": values["coverage"]["value"],
                }
            )
    if metrics:
        write_csv(output / "quality.csv", quality_rows)
    write_json(output / "costs.json", costs)

    def esc(value):
        return html.escape(str(value))

    def table(records, names=None):
        if not records:
            return "<p>Keine Einträge.</p>"
        keys = list(dict.fromkeys(k for record in records for k in record))
        return (
            "<table><thead><tr>"
            + "".join(f"<th>{esc((names or {}).get(k, k))}</th>" for k in keys)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{esc(record.get(k, ''))}</td>" for k in keys) + "</tr>"
                for record in records
            )
            + "</tbody></table>"
        )

    quality = (
        "Qualität: nicht gemessen (keine Ground Truth)."
        if not metrics
        else "Qualität: deskriptiv gegen Ground Truth."
    )
    if not metrics and summary and all(value.get("output_kind") == "ocr_text" for value in summary.values()):
        quality = "Reine OCR-Ausgabe: CER/WER mit evaluate-ocr separat prüfen; keine strukturierte Feldbewertung."
    pages = [
        {
            "Datei": Path(p["source_path"]).name,
            "Seite": p["page_number"],
            "Bildvorbereitung": p["status"],
            "Zusätzliche Drehung": f"{p.get('additional_rotation_clockwise', 0)}°",
            "Ausrichtungsmethode": p.get("orientation_method", "historisch nicht protokolliert"),
            "Ausrichtungsstatus": p.get("orientation_status", "historisch nicht protokolliert"),
            "Ausrichtung prüfen": p["review_required"] if p["status"] == "ready" else "Bildfehler",
            **({"Manuell ausgewählt": p["include"]} if manifest.get("curated") else {}),
        }
        for p in manifest["pages"]
    ]
    previews = "".join(
        f'<details><summary>{esc(p["page_id"])}</summary><a href="pages/{esc(p["page_id"])}.png">'
        f'<img loading="lazy" width="500" src="pages/{esc(p["page_id"])}.png" alt="Seitenvorschau"></a></details>'
        for p in manifest["pages"]
        if p["status"] == "ready"
    )
    readings = "".join(
        f'<details><summary>{esc(row["source_file"])} – Seite {row["page_number"]} '
        f'({esc(row["method"])}): {esc(row["status"])}, {row["participants"]} Teilnehmende</summary>'
        + (f'<p>{esc(row["error"])}</p>' if row["error"] else "")
        + (f'<p>{esc(row["review_notes"])}</p>' if row["review_notes"] else "")
        + ('<p>Teilnehmer konnten nicht strukturiert erkannt werden. '
           'Der folgende Text bleibt zur manuellen Prüfung erhalten:</p>'
           + (f'<pre>{esc(row["page_text"])}</pre>' if row["page_text"] else '<p>Kein lesbarer Text erkannt.</p>')
           if row["text_fallback"] else "")
        + "<p>" + " · ".join(f'<a href="{esc(path)}">{esc(label)}</a>' for path, label in links)
        + "</p></details>"
        for row, links in page_outputs if row["text_fallback"] or row["error"] or row["status"] == "partial"
    )
    diagnostics = "".join(
        f'<p>{esc(row["source_file"])} – Seite {row["page_number"]} ({esc(row["method"])}): '
        + " · ".join(f'<a href="{esc(path)}">{esc(label)}</a>' for path, label in links)
        + "</p>"
        for row, links in page_outputs if links
    )
    ocr_view = "".join(
        f'<details><summary>{esc(row["source_file"])} – Seite {row["page_number"]} '
        f'({esc(row["method"])}): '
        + (f'{row["word_count"]} OCR-Wörter' if row["word_count"] is not None else 'OCR-Dokumenttext')
        + '</summary>'
        f'<pre>{esc(row["text"])}</pre><p>'
        + " · ".join(f'<a href="{esc(path)}">{esc(label)}</a>' for path, label in row["links"])
        + "</p></details>" for row in ocr_records
    )
    signature_view = "".join(
        f'<details><summary>{esc(row["source_file"])} – Seite {row["page_number"]}, '
        f'Ausgabezeile {row["output_index"] + 1} ({esc(row["method"])}): '
        f'{esc(row["signature_present"])}, {esc(row["evidence"])}</summary>'
        + f'<p>Bisherige Entscheidung: {esc(row["prior_signature_present"])}; '
          f'Detailprüfung: {esc(row["detail_signature_present"])}; '
          f'übernommen: {esc(row["signature_present"])}</p>'
        + (f'<p>{esc(row["error"])}</p>' if row["error"] else "")
        + (f'<a href="{esc(row["crop"])}"><img loading="lazy" width="1100" '
           f'src="{esc(row["crop"])}" alt="Spaltenkontext und ausgewählte Teilnehmerzeile"></a>' if row["crop"] else "")
        + '</details>' for row in signature_records
    )
    selection_note = (
        "Die Eingabeseiten gehen ohne automatische Prüfung auf Dokumentart in die Extraktion."
        if manifest.get("automatic_page_selection") is False else
        "Historischer Lauf: Die damalige Seitenvorbereitung ist im Manifest dokumentiert."
    )
    content = f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'">
<title>PDF-Auslesung und Teilnehmerextraktion</title><style>body{{font:15px system-ui;margin:2rem;background:#fafafa;color:#17212d}}
table{{border-collapse:collapse;display:block;overflow:auto;margin-bottom:2rem}}th,td{{border:1px solid #bcc;padding:.5rem;
text-align:left;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{max-width:100%;height:auto}}</style>
<h1>PDF-Auslesung und Teilnehmerextraktion</h1><p>{esc(selection_note)}</p>
{('<p><a href="hybrid_analysis.html">VLM und OCR-VLM: korrigierte und verschlechterte Felder vergleichen</a></p>' if (output / 'hybrid_analysis.html').is_file() else '')}
<p>„Antworten mit gültigem Format“ zählt lesbare strukturierte Modellantworten.
Dies ist keine Bewertung, ob eine PDF-Seite eine Anwesenheitsliste ist.
Die Ausrichtungsprüfung betrifft ausschließlich die Drehung des Seitenbildes.</p>
<p>Vorrangig werden Teilnehmerdaten extrahiert. Wenn keine Teilnehmer erkannt werden,
bleibt der gelesene Seitentext als Fallback zur manuellen Prüfung erhalten.</p>
<p>{esc(quality)}</p><p>Personenbezogene Inhalte: Bericht bleibt lokal.
Keine globale Siegerkennzahl. Synthetische Tests belegen keine Qualität auf realen Listen.</p>
<h2>Ergebnis der Extraktion</h2>{table(overview)}
<h2>Dokumentweite Zuordnung von Vor- und Nachname</h2>
<p>Standard ist Nachname zuerst, danach sämtliche Vornamen. Ein eindeutiges Komma trennt die vollständigen
Namensgruppen; zusammengesetzte Nachnamen bleiben zusammen. Klare getrennte Namensspalten haben Vorrang.
Die Tabelle kennzeichnet Dokumentbelege und die vorgegebene Standardannahme getrennt. Bereits gelesene
Namensfelder werden anhand ihrer Quellzellen zugeordnet; die Schreibweise bleibt erhalten. Unklare oder
widersprüchliche Aufteilungen erfordern manuelle Prüfung. Die Excel-Referenz wird nicht herangezogen.</p>
<p><a href="document_name_orders.csv">Entscheidungen und Begründungen als CSV</a>.</p>
{table([{**row, 'name_order': {'given_family': 'Vorname → Nachname', 'family_given': 'Nachname → Vorname', 'unknown': 'Unklar'}.get(row['name_order'], row['name_order'])} for row in name_orders],
       {'method': 'Modell', 'source_file': 'PDF-Datei', 'document_id': 'Dokument-ID', 'page_number': 'PDF-Seite',
        'origin_page': 'Entscheidung auf Seite', 'name_order': 'Namensreihenfolge', 'evidence': 'Begründung',
        'decision_source': 'Entscheidungsquelle (model / user_default)', 'split_rows': 'Neu getrennte Namenszellen',
        'swapped_rows': 'Umgeordnete Namenspaare', 'review_rows': 'Prüffälle', 'conflict': 'Widerspruch'})}
<h2>Extrahierte Teilnehmerdaten</h2>
<p><a href="participants.xlsx">Teilnehmer als Excel-Datei mit Referenz-Spaltennamen</a></p>
{table(rows, dict(labels, **{name + '_state': labels[name] + ' – Status' for name in TEXT_FIELDS}))}
<details><summary>{len(excluded_instructors)} Kursleiter-/Trainereinträge ausgeschlossen</summary>
<p>Ausdrücklich belegte Kursleiterrollen sind von Teilnehmerexport, Unterschriftenprüfung und
Excel-Abgleich ausgeschlossen. <a href="excluded_instructors.csv">Ausschlussprotokoll als CSV</a>.</p>
{table(excluded_instructors)}</details>
<h2>Unterschriften im Detail</h2>
<p>Eine zusätzliche VLM-Prüfung betrachtet vergrößerte Zeilen mit Spaltenkontext.
Nur die ausgewählte Zeile unter dem blauen Trenner wird bewertet. True bedeutet sichtbare
Unterschriftspräsenz, False ein erkennbar leeres Feld, None ein unklares Ergebnis.
Dies bestätigt weder die Identität noch die Echtheit einer Unterschrift.</p>
<p>Bleibt die Detailprüfung unklar, kann eine vorhandene Entscheidung des Gesamtbilds erhalten bleiben.
Dies ist kein zusätzlicher positiver Detailbefund; die Werte werden getrennt angezeigt.</p>
{signature_view or '<p>Für diesen Lauf ist keine zusätzliche Detailprüfung gespeichert.</p>'}
<h2>Seitenübergreifende Spaltenzuordnung</h2>
<p>Geerbte Überschriften beschreiben ausschließlich die Struktur derselben PDF.
Werte stammen weiterhin aus der aktuellen Seite. Geometrische Kompatibilität ist keine OCR-Konfidenz.</p>
<p>Spaltenindizes beginnen bei 0; X-Grenzen sind Anteile der Seitenbreite. Die Tabelle nennt
die übernommenen Feldspalten, ihre Überschriftenquelle und den gemessenen Geometrievergleich.
Aktuelle eindeutige Überschriften haben Vorrang. Fehlende historische Angaben bleiben unbekannt.</p>
<p><a href="document_column_mappings.csv">Herkunft und Kompatibilitätsprüfung als CSV</a>.</p>
{table(column_mappings, {'method': 'Verfahren', 'document_id': 'PDF-ID', 'page_number': 'Seite',
    'source_page': 'Überschriften von Seite', 'status': 'Entscheidung', 'explanation': 'Begründung',
    'column_mapping': 'Feld → Spaltenindex', 'headings': 'Überschriftenbelege',
    'geometry': 'Aktuelle Geometrie', 'geometry_check': 'Vergleich mit Quellseite'})}
<h2>OCR-Beobachtungen und nicht zugeordnete Texte</h2>
<p>Alle nichtleeren gespeicherten Engine-Beobachtungen bleiben unabhängig vom Score erhalten.
Unzugeordnete Beobachtungen zählen nicht als Teilnehmerfelder. Historische Docling-Daten
enthalten nur die damals gespeicherten Zellen nach der SDK-Zusammenführung;
neu erfasste Rohbeobachtungen liegen zusätzlich davor vor.</p>
{''.join(observation_views) or '<p>Keine OCR-Beobachtungen gespeichert.</p>'}
<h2>OCR-Klartext und Modelleingabe</h2>
<p>Diese Ansicht zeigt alle OCR-Wörter als lesbaren Text, auch wenn Teilnehmer erkannt wurden.
Das OCR-Sprachmodell erhält daraus lesbare Zeilen und Zellen mit nachvollziehbaren Positionsbelegen.
Der Link „Exakte LLM-Eingabe“ zeigt den tatsächlich übergebenen Text und seine Struktur;
Systemanweisungen stehen in prompts.json. Der Klartext kann Erkennungsfehler enthalten.</p>
{ocr_view or '<p>Für diesen Lauf sind keine OCR-Daten gespeichert.</p>'}
<h2>Text-Fallback und Prüfhinweise</h2>{readings or '<p>Kein Text-Fallback oder zusätzlicher Prüfhinweis.</p>'}
<details><summary>Modellantworten zur technischen Kontrolle</summary>{diagnostics}</details>
<details><summary>Technische Bildvorbereitung</summary>{table(pages)}</details>
<details><summary>Laufzeiten und Ressourcen</summary>{table([dict(method=m, **s) for m, s in summary.items()])}</details>
<h2>Metriken mit Zählern und Nennern</h2><pre>{esc(json.dumps(metrics, ensure_ascii=False, indent=2))}</pre>
<h2>Definitionen und Grenzen</h2><pre>{esc(json.dumps(DEFINITIONS, ensure_ascii=False, indent=2))}</pre>
<p>A: Zeilenumbrüche, verschobene Spalten, verbundene Zellen und schlechte Scans können Zuordnungen stören.
Der konservative OpenCV-Modus entscheidet nur leere lokalisierte Unterschriftsfelder negativ.
Bei signature.backend=vlm (auch local_vlm) nutzen strukturierte Verfahren eine gemeinsame, separat protokollierte Signaturprüfung.
Reine OCR-Ausgaben (output_kind=ocr_text) werden nicht als Teilnehmerextraktion bewertet.
Unlimited-OCR ermittelt keine Unterschriftenpräsenz aus dem Fehlen von OCR-Text.
Das unter models.vlm konfigurierte Backend bestimmt dabei den Ausführungsort.
Sichtbare Unterschriftspräsenz ist kein Echtheitsnachweis. Eingabeseiten werden vorab manuell ausgewählt;
der Lauf führt keine automatische Seitenklassifikation durch. Orientierung anhand der Vorschau prüfen.</p>
<h2>Kostenannahmen</h2><pre>{esc(json.dumps(costs, ensure_ascii=False, indent=2))}</pre>
<h2>Seitenvorschauen</h2>{previews}</html>"""
    (output / "report.html").write_text(content, encoding="utf-8")


def refresh_report(output: Path) -> Path:
    """Regenerate exports from saved evidence without changing predictions or running models."""
    summary = read_json(output / "summary.json")
    results = {
        method: [PageResult.model_validate(row) for row in read_jsonl(output / method / "extractions.jsonl")]
        for method in summary
    }
    report(output, summary, results, read_json(output / "metrics.json"),
           read_json(output / "manifest.json"), read_json(output / "costs.json"),
           columns=read_json(output / "column_names.json") if (output / "column_names.json").is_file() else None)
    return output / "report.html"
