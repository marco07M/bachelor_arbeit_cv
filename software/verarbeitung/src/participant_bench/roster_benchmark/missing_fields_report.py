"""Offline document-review UI over the existing immutable field grading ledger."""

import json
from pathlib import Path
from types import SimpleNamespace

from ..io import digest, file_hash, write_csv, write_json
from .detail_report import document, esc, table
from .document_availability import AVAILABILITY, CAUSES, build, review_template
from .error_report import crop, relative_link
from .field_assessment import LABELS
from .matching import FIELDS

SCRIPT = r"""(() => {
const data=JSON.parse(document.getElementById('review-data').textContent),$=id=>document.getElementById(id);
const key='document-review:'+data.storage_key;let drafts={};
try{drafts=JSON.parse(localStorage.getItem(key)||'{}');}catch(e){}
const refs=Object.fromEntries(data.fields.map(f=>[f.field_id,f]));
const message=text=>{$('review-message').textContent=text;};
const controls=['method','document','field','schriftart','cause','availability'];
const apply=()=>{let n=0;for(const row of document.querySelectorAll('tr.field-cause')){
 const show=controls.every(k=>!$(k).value||(k==='document'?row.dataset.documents.split('|').includes($(k).value):row.dataset[k]===$(k).value))&&
 (!$('only-missing').checked||row.dataset.missing==='true')&&row.textContent.toLocaleLowerCase().includes($('search').value.toLocaleLowerCase());
 row.hidden=!show;if(show)n++;}$('visible-count').textContent=String(n);};
for(const id of [...controls,'search','only-missing'])$(id).addEventListener('input',apply);apply();
function review(){return drafts[$('review-key').value]||data.reviews[$('review-key').value]||{availability:'unchecked',locations:[]};}
function setPages(){const d=data.documents[$('review-doc').value];$('review-page').replaceChildren();
 for(const n of d?.pages||[]){const o=document.createElement('option');o.value=n;o.textContent=String(n);$('review-page').append(o);}showImage();}
function showImage(){const d=data.documents[$('review-doc').value],n=$('review-page').value,p=d?.page_links?.[n];
 $('review-image').hidden=!p;if(p)$('review-image').src=p;
 $('review-pdf').hidden=!d?.pdf_link;if(d?.pdf_link)$('review-pdf').href=d.pdf_link+'#page='+n;}
function load(){const f=refs[$('review-key').value],r=review();$('review-reference').textContent=f.participant+' · '+f.field+' · Referenz: '+JSON.stringify(f.reference_value);
 $('review-doc').replaceChildren();for(const id of f.documents){const d=data.documents[id],o=document.createElement('option');o.value=id;o.textContent=d.name+(!d.verified?' (Original nicht verifiziert)':'');$('review-doc').append(o);}
 if(r.locations?.[0])$('review-doc').value=r.locations[0].document_id;setPages();if(r.locations?.[0])$('review-page').value=r.locations[0].page_number;showImage();
 $('review-availability').value=r.availability||'unchecked';for(const k of ['document_value','reviewer','anchor_note','note'])$('review-'+k).value=r[k]||'';
 $('review-independent').checked=r.independent_of_predictions===true;$('review-person').checked=r.reference_person_verified===true;
 $('review-all-pages').checked=(r.reviewed_pages?.length||0)===f.documents.reduce((n,d)=>n+data.documents[d].pages.length,0);
 for(const k of ['x0','y0','x1','y1'])$('review-'+k).value=r.locations?.[0]?.bbox?.[k]??'';
 $('review-pages-list').textContent=f.documents.map(d=>data.documents[d].name+': Seiten '+data.documents[d].pages.join(', ')).join(' · ');
 message(drafts[f.field_id]?'Lokaler Entwurf geladen. Gespeicherte Kennzahlen unverändert.':'Originalprüfung ohne Modellausgabe; verfügbare Modellbelege stehen getrennt unten.');}
$('review-key').addEventListener('change',load);$('review-doc').addEventListener('change',setPages);$('review-page').addEventListener('change',showImage);
for(const button of document.querySelectorAll('[data-review-field]'))button.addEventListener('click',()=>{$('review-key').value=button.dataset.reviewField;load();$('document-review').open=true;$('document-review').scrollIntoView({behavior:'smooth'});});
$('review-save').addEventListener('click',()=>{try{
 const f=refs[$('review-key').value],r={field_id:f.field_id,availability:$('review-availability').value,review_method:'manual_pdf_review',
 independent_of_predictions:$('review-independent').checked,reference_person_verified:$('review-person').checked,reviewed_at:new Date().toISOString()};
 for(const k of ['document_value','reviewer','anchor_note','note'])r[k]=$('review-'+k).value.trim();
 const parts=['x0','y0','x1','y1'].map(k=>$('review-'+k).value.trim());let box=null;
 if(parts.some(v=>v!=='')){if(parts.some(v=>v===''))throw Error('Ausschnitt: alle vier Koordinaten angeben.');const v=parts.map(Number);
  if(v.some(x=>!Number.isFinite(x)||x<0||x>1)||v[0]>=v[2]||v[1]>=v[3])throw Error('Ungültiger Originalausschnitt.');box=Object.fromEntries(['x0','y0','x1','y1'].map((k,i)=>[k,v[i]]));}
 r.locations=$('review-doc').value?[{document_id:$('review-doc').value,page_number:Number($('review-page').value),bbox:box},...(review().locations||[]).slice(1)]:[];
 r.reviewed_pages=$('review-all-pages').checked?f.documents.flatMap(d=>data.documents[d].pages.map(n=>({document_id:d,page_number:n}))):[];
 if(['readable','unreadable','absent'].includes(r.availability)){
  if(!r.independent_of_predictions||!r.reference_person_verified||!r.reviewer||!r.anchor_note||!r.note)throw Error('Unabhängige Prüfung, Personenzuordnung, Prüfer und Begründungen bestätigen.');
  if(!r.locations.length||r.locations.some(l=>!data.documents[l.document_id]?.verified))throw Error('Verifiziertes Original und Seite erforderlich.');
  if(r.availability==='readable'&&!r.document_value)throw Error('Lesbaren Originalwert unabhängig transkribieren.');
  if(r.availability==='absent'&&!$('review-all-pages').checked)throw Error('Abwesenheit erfordert die Prüfung aller aufgeführten Kursseiten.');
 }
 drafts[f.field_id]=r;try{localStorage.setItem(key,JSON.stringify(drafts));}catch(e){}
 message('Entwurf gespeichert. Exportieren und mit --document-annotations in einen neuen Bericht übernehmen. Die angezeigten Kennzahlen bleiben eingefroren.');
 }catch(e){message(e.message);}});
$('review-export').addEventListener('click',()=>{const annotations=data.fields.map(f=>{const r=drafts[f.field_id]||data.reviews[f.field_id]||{field_id:f.field_id,availability:'unchecked'};
 const clean={...r};delete clean.eligible;delete clean.reference_agrees;return clean;});
 const original_documents=Object.fromEntries(Object.entries(data.documents).filter(([k,d])=>d.verified).map(([k,d])=>[k,d.path]));
 const url=URL.createObjectURL(new Blob([JSON.stringify({...data.binding,original_documents,annotations},null,2)],{type:'application/json'})),a=document.createElement('a');
 a.href=url;a.download='dokumentpruefung.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('review-import').addEventListener('change',async()=>{try{const value=JSON.parse(await $('review-import').files[0].text());
 for(const k of ['version','reference_snapshot_sha256','documents'])if(JSON.stringify(value[k])!==JSON.stringify(data.binding[k]))throw Error('Annotation gehört zu einer anderen Referenz-/PDF-Datenbasis.');
 const next={};for(const r of value.annotations){if(!refs[r.field_id]||next[r.field_id]||!data.availability[r.availability])throw Error('Unbekannte oder doppelte Annotation.');next[r.field_id]=r;}
 drafts=next;try{localStorage.setItem(key,JSON.stringify(drafts));}catch(e){}load();message('Entwürfe importiert; verbindliche Validierung und Neuberechnung erfolgen durch Python im neuen Bericht.');
 }catch(e){message('Import fehlgeschlagen: '+e.message);}});
if(data.fields.length)load();
})();"""


def original_pages(output, ctx):
    """Render verified ORIGINAL PDFs, never infer legibility from OCR or model images."""
    import pymupdf

    root = output / "missing_fields/originals"
    (root / "pages").mkdir(parents=True, exist_ok=True)
    documents = {}
    for key, doc in ctx["documents"].items():
        value = dict(doc, page_links={}, pdf_link=None)
        if doc["verified"]:
            value["pdf_link"] = relative_link(Path(doc["path"]), output)
            with pymupdf.open(doc["path"]) as pdf:
                for number in doc["pages"]:
                    if number > len(pdf):
                        raise ValueError("Original-PDF enthält die gespeicherte Seite nicht")
                    path = root / "pages" / f"{key}-p{number:04d}.png"
                    if not path.is_file():
                        pdf[number - 1].get_pixmap(dpi=150).save(path)
                    value["page_links"][number] = relative_link(path, output)
            if file_hash(Path(doc["path"])) != key:
                raise ValueError("Original-PDF wurde während der Dokumentprüfung verändert")
        documents[key] = value
    return root, documents


def number(value):
    return "nicht definiert" if value is None else f"{100 * value:.2f} %".replace(".", ",")


def select(identifier, label, choices):
    return (
        f'<label>{esc(label)} <select id="{identifier}"><option value="">Alle</option>'
        + "".join(f'<option value="{esc(k)}">{esc(v)}</option>' for k, v in choices)
        + "</select></label>"
    )


def render(output, annotation_path=None):
    output = Path(output).resolve()
    payload, ctx = build(output, annotation_path)
    folder = output / "missing_fields"
    folder.mkdir(exist_ok=True)
    originals, documents = original_pages(output, ctx)
    write_json(folder / "analysis.json", payload)
    refs = {r["field_id"]: r for r in payload["fields"]}
    write_json(folder / "annotations.template.json", review_template(refs, ctx))
    write_json(
        folder / "annotations.snapshot.json",
        dict(
            **payload["binding"],
            original_documents={k: d["path"] for k, d in ctx["documents"].items() if d["verified"]},
            annotations=list(payload["reviews"].values()),
        ),
    )
    content = '<h1>Ursachen fehlender Felder</h1><p><a href="report.html">Ergebnisbericht</a> · <a href="extraction_errors.html">Gespeicherte Verarbeitungskette</a> · <a href="missing_fields/analysis.json">Analyse JSON</a> · <a href="missing_fields/cases.csv">Feldfälle CSV</a></p>'
    content += '<div class="box">Referenz-Ground-Truth und unabhängig geprüfter Dokumentinhalt sind verschiedene Bewertungsgrundlagen. Fehlende Ausgaben oder OCR-Beobachtungen beweisen keine leere Zelle. Nur explizite Originalprüfung setzt Verfügbarkeit. Ungeprüfte Fälle bleiben vollständig in den bisherigen Metriken. Neue bedingte Kennzahlen sind weder eine Gesamtnote noch eine Schätzung für ungeprüfte Felder.</div>'
    unavailable = [d["name"] for d in documents.values() if not d["verified"]]
    if unavailable:
        content += (
            '<p class="box"><strong>Original nicht verifiziert:</strong> '
            + esc(", ".join(unavailable))
            + ". Die Datei fehlt, ist nicht lesbar oder ihre Prüfsumme weicht vom eingefrorenen Lauf ab. Laufbilder/OCR sind kein Ersatz für die unabhängige Originalprüfung. Geprüfte Labels benötigen die damalige PDF-Version; ein gleicher Dateiname genügt nicht.</p>"
        )
    content += "<h2>Getrennte Bewertungsgrundlagen und Nenner</h2>"
    content += table(
        [
            "Verfahren",
            "Referenzfelder R",
            "Geprüft",
            "Lesbar, Wert wie Referenz R_doc",
            "Lesbar, abweichender Dokumentwert",
            "Ungeprüft / unklar",
            "Exact Recall bisher / Dokumentteilmenge",
            "Exact F1 bisher / bedingte Teilmenge",
            "Coverage bisher / Teilmenge",
            "Ø Ähnlichkeit bisher / Teilmenge",
            "Teilmenge: exakt / falsch / fehlend / D",
        ],
        [
            [
                m,
                p["expected_fields"],
                p["reviewed_fields"],
                p["eligible_fields"],
                p["readable_reference_conflicts"],
                p["availability_counts"].get("unchecked", 0) + p["availability_counts"].get("uncertain", 0),
                *(
                    number(p["baseline"][k]) + " / " + number(p["readable_reference_subset"][k])
                    for k in ("exact_recall", "exact_f1", "field_coverage", "detected_similarity")
                ),
                " / ".join(
                    str(p["readable_reference_subset"][k])
                    for k in ("exact_fields", "incorrect_fields", "missing_fields", "detected_fields")
                ),
            ]
            for m, p in payload["projections"].items()
        ],
    )
    content += "<p>Die Dokumentteilmenge verwendet ausschließlich unabhängig lesbar bestätigte Werte, die nach bestehender Normalisierung der Referenz entsprechen. R_doc = exakt + falsch + fehlend. Die vorhandenen Feldzähler werden auf denselben Paarungen summiert; kein neues Matching. Precision/F1 dieser Teilmenge gelten bedingt auf GT-Paare. Ungepaarte Zusatzwerte bleiben in den unveränderten globalen P-/FP-/F1-Werten. Lesbare abweichende Originalwerte sind als Referenzkonflikte separat ausgewiesen. Fehlende Felder reduzieren die bedingte Textähnlichkeit weiterhin nicht; ihr Nenner ist D.</p>"
    content += "<p>Eine teilweise geprüfte, gezielt ausgewählte Dokumentmenge ist nicht repräsentativ. Scoreunterschiede zur lesbaren Teilmenge sind kein kausaler Bereinigungsfaktor für alle Dokumente. Art und Autor jeder Sichtprüfung stehen im JSON-Protokoll; eine einzelne assistierte Sichtprüfung ersetzt keine unabhängig doppelt annotierte Dokument-Ground-Truth.</p>"
    content += "<p>Dokumentverfügbarkeit wird einmal je Referenzfeld annotiert und für alle Verfahren wiederverwendet. Die Prüfzahlen verschiedener Verfahren sind keine unabhängigen Stichproben.</p>"
    content += (
        "<details><summary>Bestehende Normalisierung für Referenz-/Dokumentvergleich</summary>"
        + table(["Option", "Wert"], list(payload["normalization"].items()))
        + "<p>NFC und Leerzeichenbehandlung wie im eingefrorenen Vergleich. ID-Nullen und Groß-/Kleinschreibung folgen dessen Optionen; keine neue Umlaut-, Schreibfehler- oder Levenshtein-Toleranz. Auch formale Abweichungen können deshalb als Referenzabweichung erscheinen. Dies ist kein automatischer Nachweis einer sachlich falschen Referenz.</p></details>"
    )
    content += table(
        [
            "Verfahren",
            "Belegt nicht vorhanden: erwartet / exakt / falsch / fehlend",
            "Belegt unleserlich: erwartet / exakt / falsch / fehlend",
        ],
        [
            [
                m,
                *(
                    " / ".join(
                        str(p["availability_contributions"][state][k])
                        for k in ("reference_fields", "exact_fields", "incorrect_fields", "missing_fields")
                    )
                    for state in ("absent", "unreadable")
                ),
            ]
            for m, p in payload["projections"].items()
        ],
    )
    content += "<h2>Fehlende Felder nach Ursache</h2>"
    content += table(
        ["Verfahren", *CAUSES.values(), "Fehlende Felder gesamt"],
        [[m, *(p.get(k, 0) for k in CAUSES), sum(p.values())] for m, p in payload["missing_causes"].items()],
    )
    content += "<p>„Dokument geprüft“ belegt eine manuelle Originalprüfung. „Verarbeitungsschritt belegt“ bestätigt einen gespeicherten Übergang, keine Dokumentlesbarkeit oder korrekte Modelltranskription. „Vermutung“ ist keine bewiesene Ursache. Gleichlautende Texte in anderen Ausgabefeldern liefern ausschließlich Zuordnungshinweise. Beim direkten VLM gibt es keinen vorgeschalteten OCR-Schritt.</p>"
    if "docling" not in payload["projections"]:
        content += "<p>Docling ist in diesem Vergleich nicht enthalten. Ergebnisse anderer Dokumentmengen werden nicht stillschweigend hinzugefügt.</p>"
    content += (
        '<details id="document-review"><summary>Unabhängige Dokumentprüfung und manuelle Annotation</summary>'
    )
    content += "<p>Original prüfen, ohne die Modellausgabe als Beleg zu verwenden. Erst Person unabhängig zuordnen, dann Inhalt und Lesbarkeit beurteilen. Entwürfe bleiben lokal im Browser; sie ändern keine gespeicherten Scores. JSON exportieren und mit <code>analyze --report ALT --output NEU --document-annotations dokumentpruefung.json</code> übernehmen. Python validiert Herkunft, Prüfprotokoll und Dokumentbezug. Die ursprüngliche Referenz wird nicht geändert.</p>"
    content += (
        '<label>Referenzfeld <select id="review-key">'
        + "".join(
            f'<option value="{esc(r["field_id"])}">{esc(r["class_id"])} · GT {esc(r["reference_row"])} · {esc(r["participant"])} · {esc(r["field"])}</option>'
            for r in payload["fields"]
        )
        + '</select></label><p id="review-reference"></p>'
    )
    content += '<label>Originaldokument <select id="review-doc"></select></label><label>Seite <select id="review-page"></select></label> <a id="review-pdf" target="_blank" rel="noopener">Original-PDF öffnen</a><br><img id="review-image" loading="lazy" style="max-width:100%;max-height:850px;object-fit:contain" alt="Unabhängig gerenderte Originalseite"><br>'
    content += (
        '<label>Verfügbarkeit <select id="review-availability">'
        + "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in AVAILABILITY.items())
        + "</select></label>"
    )
    for key, label in [
        ("document_value", "Unabhängig gelesener Originalwert"),
        ("reviewer", "Prüfer"),
        ("anchor_note", "Unabhängiger Personenanker"),
        ("note", "Begründung / Befund"),
    ]:
        content += f'<label>{esc(label)} <input id="review-{key}" type="text"></label>'
    content += (
        "<p>Ausschnitt auf der Originalseite, normiert 0–1 (optional): "
        + "".join(
            f'<label>{k} <input id="review-{k}" type="number" min="0" max="1" step="0.001"></label>'
            for k in ("x0", "y0", "x1", "y1")
        )
        + "</p>"
    )
    content += '<label><input id="review-person" type="checkbox">Person unabhängig im Original zugeordnet</label><label><input id="review-independent" type="checkbox">Verfügbarkeit unabhängig von Modellausgaben geprüft</label><br><label><input id="review-all-pages" type="checkbox">Alle Kursseiten auf Abwesenheit geprüft</label><p id="review-pages-list"></p>'
    content += '<button id="review-save" type="button">Entwurf speichern</button><button id="review-export" type="button">Annotationen als JSON exportieren</button><label>Entwürfe importieren <input id="review-import" type="file" accept="application/json,.json"></label><p id="review-message" role="status"></p></details>'
    methods = sorted(payload["projections"])
    content += (
        '<div class="filters">'
        + select("method", "Verfahren", [(m, m) for m in methods])
        + select("document", "Dokument", [(k, d["name"]) for k, d in documents.items()])
    )
    content += select("field", "Feldtyp", [(f, f) for f in FIELDS]) + select(
        "schriftart",
        "GT-Schriftart",
        [
            ("h", "Handschrift"),
            ("m", "Maschinenschrift"),
            ("g", "Gemischt"),
            ("unclassified", "Nicht klassifiziert"),
        ],
    )
    content += select("cause", "Fehlerursache", CAUSES.items()) + select(
        "availability", "Dokumentverfügbarkeit", AVAILABILITY.items()
    )
    content += '<label>Suche <input id="search" type="search"></label><label><input id="only-missing" type="checkbox" checked>Nur fehlende Referenzfelder</label> · Sichtbar: <span id="visible-count"></span></div>'
    content += (
        '<div class="scroll"><table><thead><tr>'
        + "".join(
            "<th>" + esc(h) + "</th>"
            for h in [
                "Verfahren / Pipeline",
                "Dokument / Ausgabeseite",
                "Teilnehmer / Feld / Schriftart",
                "Ground Truth",
                "Extrahierter Originalwert / Status",
                "Dokumentverfügbarkeit / Originalwert",
                "Ursache / Beleglage",
                "OCR-/Modellbelege",
                "Original / Ausschnitt / Prüfung",
            ]
        )
        + "</tr></thead><tbody>"
    )
    certainty_labels = dict(
        document_verified="Dokument geprüft",
        stage_verified="Verarbeitungsschritt belegt",
        hypothesis="Vermutung",
        unknown="Unbekannt",
    )
    for row in payload["cases"]:
        reference = refs[row["field_id"]]
        review = row["review"]
        ids = reference["documents"]
        doc_label = documents.get(row.get("document_id"), {}).get("name") or " | ".join(
            documents[d]["name"] for d in ids
        )
        attrs = dict(
            method=row["candidate"],
            documents="|".join(ids),
            field=row["field"],
            schriftart=row.get("schriftart") or "unclassified",
            cause=row["cause"] or "",
            availability=row["availability"],
            missing=str(row["missing"]).lower(),
        )
        content += (
            '<tr class="field-cause" ' + " ".join(f'data-{k}="{esc(v)}"' for k, v in attrs.items()) + ">"
        )
        content += "".join(
            "<td>" + esc(v) + "</td>"
            for v in [
                row["candidate"] + "\n" + row["pipeline"],
                doc_label + " · " + str(row.get("page_number") or "Seite nicht zugeordnet"),
                reference["participant"]
                + "\nGT "
                + str(row["reference_row"])
                + " · "
                + row["field"]
                + " · "
                + str(row.get("schriftart") or "nicht klassifiziert"),
                row["reference_value"],
                str(row.get("original_prediction_value")) + "\n" + LABELS[row["evaluation_status"]],
                AVAILABILITY[row["availability"]]
                + "\nOriginalwert: "
                + str(review.get("document_value"))
                + "\n"
                + str(review.get("note") or "")
                + "\nPrüfung: "
                + str(review.get("reviewer") or "offen")
                + " · "
                + str(review.get("reviewed_at") or "")
                + " · "
                + str(review.get("review_method") or ""),
                (CAUSES.get(row["cause"]) or "Kein fehlendes Feld")
                + "\n"
                + certainty_labels.get(row["certainty"], "")
                + "\n"
                + str(row["cause_reason"] or ""),
            ]
        )
        diagnosis = row["diagnosis"]
        content += (
            "<td><details><summary>Gespeicherte Belege</summary><pre>"
            + esc(
                json.dumps(
                    dict(
                        observations=diagnosis.get("observations", []),
                        pipeline=diagnosis.get("pipeline_trace", {}),
                        auxiliary_position_ocr_not_primary_vlm_input=diagnosis.get(
                            "auxiliary_ocr_observations", []
                        ),
                        stage_reason=diagnosis.get("reason"),
                        assignment_hints=row["assignment_hints"],
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details></td><td>"
        )
        for loc in review.get("locations") or []:
            doc = documents[loc["document_id"]]
            if doc["pdf_link"]:
                content += f'<a href="{esc(doc["pdf_link"])}#page={loc["page_number"]}">{esc(doc["name"])} · geprüfte Originalseite {loc["page_number"]}</a><br>'
            href = crop(
                originals,
                output,
                SimpleNamespace(page_id=f"{loc['document_id']}-p{loc['page_number']:04d}"),
                loc.get("bbox"),
                ("availability", row["field_id"], loc),
            )
            if href:
                content += f'<a href="{esc(href)}"><img loading="lazy" style="max-width:300px;max-height:150px" src="{esc(href)}" alt="Unabhängig geprüfter Originalausschnitt"></a><br>'
        if not review.get("locations"):
            for d in ids:
                if documents[d]["pdf_link"]:
                    content += f'<a href="{esc(documents[d]["pdf_link"])}">{esc(documents[d]["name"])} (Kursbezug, keine Feldlokalisierung)</a><br>'
        content += f'<button type="button" data-review-field="{row["field_id"]}">Original prüfen / annotieren</button></td></tr>'
    content += "</tbody></table></div><p>Signaturen sind keine Textfelder. GT-Schriftart ist eine Teilnehmerannotation; g erlaubt keine feldgenaue Handschriftzuordnung. Bildausschnitte hier stammen aus unabhängig geprüften Originalpositionen. Modellregionen und Rohantworten stehen getrennt in der Verarbeitungskette.</p>"
    ui = dict(
        fields=payload["fields"],
        reviews=payload["reviews"],
        binding=payload["binding"],
        documents=documents,
        availability=AVAILABILITY,
        storage_key=digest(payload["binding"]),
    )
    content += (
        '<script type="application/json" id="review-data">'
        + json.dumps(ui, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>"
    )
    path = output / "missing_fields.html"
    path.write_text(document("Ursachen fehlender Felder", content, script_source=SCRIPT), encoding="utf8")
    csv_rows = [
        dict(
            method=r["candidate"],
            class_id=r["class_id"],
            reference_row=r["reference_row"],
            document_id=r["document_id"],
            page_number=r["page_number"],
            field=r["field"],
            schriftart=r.get("schriftart"),
            ground_truth=r["reference_value"],
            prediction=r.get("original_prediction_value"),
            missing=r["missing"],
            availability=r["availability"],
            document_value=r["review"].get("document_value"),
            cause=r["cause"],
            certainty=r["certainty"],
            reason=r["cause_reason"],
        )
        for r in payload["cases"]
    ]
    write_csv(folder / "cases.csv", csv_rows, fields=None if csv_rows else ["method", "field", "cause"])
    write_json(
        folder / "checks.json",
        dict(
            baseline_unchanged=True,
            matching_unchanged=True,
            missing_partition={
                m: sum(v.values()) == payload["projections"][m]["baseline"]["missing_fields"]
                for m, v in payload["missing_causes"].items()
            },
            annotation_sha256=payload["annotation_sha256"],
            review_binding=payload["binding"],
            render_sha256=file_hash(Path(__file__)),
        ),
    )
    for name in ("report.html", "extraction_errors.html", "details.html", "standard_report.html"):
        target = output / name
        if target.is_file():
            text = target.read_text(encoding="utf8")
            if 'href="missing_fields.html"' not in text:
                target.write_text(
                    text.replace(
                        "</h1>",
                        '</h1><p><a href="missing_fields.html"><strong>Ursachen fehlender Felder</strong></a></p>',
                        1,
                    ),
                    encoding="utf8",
                )
    return path
