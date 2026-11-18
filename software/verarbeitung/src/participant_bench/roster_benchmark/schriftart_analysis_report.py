"""Handwriting vs print: presentation of existing frozen field vectors and document reviews."""

import json
from pathlib import Path

from ..io import file_hash, read_json, write_csv, write_json
from .dashboard_report import LABELS, STYLE
from .detail_report import document, esc
from .document_availability import AVAILABILITY, context
from .report import detected_percent
from .schriftart_report import analyse_fields
from .scientific_validity import load_pages

SCRIPT = r"""(() => {
const data=JSON.parse(document.getElementById('schriftanalyse-data').textContent);
const controls=Object.fromEntries(['basis','method','document','field','style'].map(k=>[k,document.getElementById('sa-'+k)]));
const styles=data.styles,colors={h:'#663da6',m:'#15629b',g:'#ad6c00',unclassified:'#6c7882'};
const pct=v=>v===null||v===undefined?'nicht definiert':(100*v).toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})+' %';
const num=v=>v===null||v===undefined?'—':v.toLocaleString('de-DE',{maximumFractionDigits:3});
const ratio=(n,d,v)=>`${pct(v)} (${num(n)}/${num(d)})`;
function table(id,rows){const body=document.getElementById(id);body.replaceChildren();
 for(const values of rows){const row=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=String(value);row.appendChild(cell);}body.appendChild(row);}}
function svgNode(svg,name,attrs,text){const node=document.createElementNS('http://www.w3.org/2000/svg',name);
 for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;svg.appendChild(node);return node;}
function chart(id,rows,kind){const svg=document.getElementById(id);svg.replaceChildren();const left=275,width=560,height=44*rows.length+40;
 svg.setAttribute('viewBox',`0 0 1250 ${Math.max(80,height)}`);svg.setAttribute('height',String(Math.max(80,height)));
 for(const v of [0,.25,.5,.75,1]){svgNode(svg,'line',{x1:left+v*width,x2:left+v*width,y1:28,y2:height,stroke:'#d6e2ec'});svgNode(svg,'text',{x:left+v*width,y:17,'text-anchor':'middle',fill:'#587084','font-size':12},`${100*v} %`);}
 for(const [index,row] of rows.entries()){const y=index*44+35;const label=(row.candidate?row.candidate+' · ':'')+styles[row.schriftart];
 svgNode(svg,'text',{x:5,y:y+17,fill:'#142d45','font-size':13},label);
 svgNode(svg,'rect',{x:left,y,width,height:24,fill:'#eef2f6'});
 let segments,detail;
 if(kind==='quality'){segments=[[row.exact_recall,'#23876b'],[row.incorrect_rate,'#e3a138'],[row.missing_rate,'#bb4651']];detail=`R=${row.reference_fields}; E=${row.exact_fields}, W=${row.incorrect_fields}, M=${row.missing_fields}`;}
 else if(kind==='distribution'){segments=[[row.reference_share,colors[row.schriftart]]];detail=`${row.reference_fields}/${row.reference_share_denominator} Felder`;}
 else{segments=[[row.combined_error_share,colors[row.schriftart]]];detail=`${row.error_fields}/${row.combined_error_denominator} Fehler`;}
 let x=left;for(const [fraction,color] of segments){if(fraction===null||fraction===undefined)continue;const w=width*Math.max(0,Math.min(1,fraction));svgNode(svg,'rect',{x,y,width:w,height:24,fill:color});x+=w;}
 const undefinedValue=kind==='quality'?row.exact_recall===null:kind==='distribution'?row.reference_share===null:row.combined_error_share===null;
 svgNode(svg,'text',{x:left+width+10,y:y+17,fill:'#142d45','font-size':12},undefinedValue?'nicht definiert · '+detail:detail);}}
function apply(){const basis=controls.basis.value,doc=controls.document.value,field=controls.field.value,method=controls.method.value,style=controls.style.value;
 const view=data.views[basis][doc][field];const groups=view.distribution.filter(r=>!style||r.schriftart===style);
 const rows=view.comparisons.filter(r=>(!method||r.candidate===method)&&(!style||r.schriftart===style));
 document.getElementById('sa-denominator').textContent=String(view.reference_fields);
 document.getElementById('sa-scope').textContent=(basis==='reference'?'Referenzbasiert':'Unabhängig lesbar und referenzgleich')+' · '+data.documents[doc].label+' · '+(field==='all'?'Alle Textfelder':data.field_labels[field]);
 table('sa-distribution',groups.map(r=>[styles[r.schriftart],r.participants,r.reference_fields,ratio(r.reference_fields,r.reference_share_denominator,r.reference_share),...Object.keys(data.field_labels).map(f=>field==='all'||field===f?r.field_counts[f]:'nicht ausgewählt')]));
 table('sa-quality',rows.map(r=>[r.candidate,styles[r.schriftart],r.reference_fields,r.exact_fields,r.incorrect_fields,r.missing_fields+(r.invalid_prediction_fields?' (davon '+r.invalid_prediction_fields+' ungültige IDs)':''),r.fully_missing_final_values,r.present_but_unusable_values,pct(r.exact_recall),pct(r.field_coverage),pct(r.detected_similarity)+' (D='+r.detected_fields+'; Σs='+num(r.detected_similarity_credit)+')',r.evaluation_status_counts.unclear]));
 table('sa-errors',rows.map(r=>[r.candidate,styles[r.schriftart],r.incorrect_fields,r.missing_fields,r.error_fields,pct(r.incorrect_rate),pct(r.missing_rate),pct(r.error_rate),ratio(r.incorrect_fields,r.incorrect_error_denominator,r.incorrect_error_share),ratio(r.missing_fields,r.missing_error_denominator,r.missing_error_share),ratio(r.error_fields,r.combined_error_denominator,r.combined_error_share)]));
 table('sa-availability',groups.map(r=>[styles[r.schriftart],r.reviewed_fields,r.eligible_fields,r.reference_conflicts,...Object.keys(data.availability).map(k=>r.availability_counts[k]||0)]));
 chart('sa-distribution-chart',groups,'distribution');chart('sa-quality-chart',rows,'quality');chart('sa-error-chart',rows,'errors');
 let n=0;for(const row of document.querySelectorAll('[data-sa-case]')){const d=row.dataset;
 const ok=(!method||d.method===method)&&(!style||d.style===style)&&(doc==='all'||d.document===doc)&&(field==='all'||d.field===field)&&(basis!=='document'||d.eligible==='true');row.hidden=!ok;if(ok)n++;}
 document.getElementById('sa-detail-count').textContent=String(n);
 document.getElementById('sa-empty-basis').hidden=view.reference_fields!==0;}
for(const control of Object.values(controls))control.addEventListener('change',apply);apply();
})();"""


def select(key, label, values):
    return (
        f'<label>{esc(label)}<select id="sa-{key}">'
        + "".join(f'<option value="{esc(k)}">{esc(v)}</option>' for k, v in values)
        + "</select></label>"
    )


def skeleton(identifier, headings):
    return (
        f'<div class="scroll {identifier}-table"><table><thead><tr>'
        + "".join(f"<th>{esc(h)}</th>" for h in headings)
        + f'</tr></thead><tbody id="{identifier}"></tbody></table></div>'
    )


def render(output, scientific):
    availability = read_json(output / "missing_fields/analysis.json")
    snapshot = read_json(output / "missing_fields/annotations.snapshot.json")
    ctx = context(output, snapshot.get("original_documents"))
    page_path = output / "scientific/page_annotations.snapshot.json"
    locations = (
        load_pages(page_path, ctx, scientific["metric_audit"]["participants"])[1]
        if page_path.is_file()
        else {}
    )
    payload = analyse_fields(scientific["metric_audit"], availability, ctx, locations)
    payload.update(
        binding=availability["binding"],
        field_grading_sha256=file_hash(output / "scientific/metric_audit.json"),
        document_review_sha256=file_hash(output / "missing_fields/analysis.json"),
        independent_page_annotation_sha256=file_hash(page_path) if page_path.is_file() else None,
        implementation_sha256=file_hash(Path(__file__)),
    )
    folder = output / "scientific"
    write_json(folder / "schriftart_analysis.json", payload)
    content = f'<style>{STYLE}.sa-chart{{width:100%;min-width:750px;display:block}}.hero{{margin-bottom:16px}}.sa-legend span{{margin-right:18px}}.sa-legend i{{display:inline-block;width:13px;height:13px;margin-right:5px}}.sa-quality-table table,.sa-errors-table table{{min-width:1850px}}.sa-quality-table td,.sa-errors-table td{{white-space:nowrap}}.sa-quality-table th,.sa-errors-table th{{overflow-wrap:normal;word-break:normal}}</style><main class="dash">'
    content += '<header class="hero"><h1>Handschrift vs. Maschinenschrift</h1><p><a href="report.html#schriftart">Gesamtbericht / Schriftartgruppen</a> · <a href="missing_fields.html">Unabhängige Dokumentprüfung</a> · <a href="scientific/schriftart_analysis.json">Analyse JSON</a> · <a href="scientific/schriftart_analysis.csv">Tabellen CSV</a></p>'
    content += "<p>Die Schriftart liegt in der Ground Truth <strong>pro Teilnehmer</strong> vor. Die vier Feldtypen werden nach dieser Teilnehmerkennzeichnung gruppiert; eine unabhängige feldgenaue Schriftannotation ist damit nicht gegeben. g bleibt eine eigene Mischkategorie. Unklassifizierte Referenzen bleiben sichtbar. Unterschriften sind ausschließlich Präsenzbefunde und aus allen Textfeldzahlen ausgeschlossen.</p>"
    if payload["missing_requested_methods"]:
        content += (
            '<p class="note">Kein vergleichbares strukturiertes Ergebnis in diesem Umfang für: '
            + esc(", ".join(payload["missing_requested_methods"]))
            + ". Fehlende Verfahren erhalten keine erfundenen Nullwerte. Separate Läufe mit anderen PDFs oder Referenzständen dürfen nicht ungeprüft zusammengeführt werden.</p>"
        )
    content += '<div class="filters">'
    content += select(
        "basis",
        "Bewertungsgrundlage",
        [
            ("reference", "Alle bewertbaren Referenzfelder"),
            ("document", "Nur unabhängig lesbar und referenzgleich"),
        ],
    )
    content += select("method", "Verfahren", [("", "Alle Verfahren"), *((m, m) for m in payload["methods"])])
    content += select(
        "document", "Dokument / Referenzumfang", [(k, v["label"]) for k, v in payload["documents"].items()]
    )
    content += select("field", "Feldtyp", [("all", "Alle Textfelder"), *LABELS.items()])
    content += select("style", "Teilnehmer-Schriftart", [("", "Alle Kategorien"), *payload["styles"].items()])
    content += '</div><p><strong>Aktueller Umfang:</strong> <span id="sa-scope"></span> · Nenner R = <strong id="sa-denominator"></strong> (ohne Schriftartfilter).</p>'
    content += '<p class="note" id="sa-empty-basis" hidden>Für diese Bewertungsgrundlage und diesen Filterumfang sind keine bewertbaren Referenzfelder vorhanden. Qualitätswerte sind nicht definiert. Dies ist keine gemessene Nullleistung.</p></header>'
    content += '<section class="hero"><h2>Verteilung der erwarteten Felder</h2><p>R zählt wie bisher bewertbare, nichtleere Referenzfelder. Die Verteilung ist methodenunabhängig und zählt die Ground Truth einmal, nicht einmal je Verfahren. Schriftartfilter blenden Kategorien aus, ändern deren Anteilsnenner aber nicht.</p>'
    content += skeleton(
        "sa-distribution",
        [
            "Teilnehmer-Schriftart",
            "Referenzpersonen",
            "Erwartete Felder R",
            "Anteil an R im Filterumfang",
            *LABELS.values(),
        ],
    )
    content += '<div class="scroll"><svg class="sa-chart" id="sa-distribution-chart" role="img" aria-label="Anteil erwarteter Felder nach Teilnehmer-Schriftart"></svg></div></section>'
    content += '<section class="hero"><h2>Erkennungsqualität nach Teilnehmer-Schriftart</h2>'
    content += "<p>Vorhandene Matchingentscheidungen, Normalisierung und Feldzähler bleiben unverändert. Exakte Feldtreffer E bestätigen keine unsichere Personenidentität; unklare Zuordnungen werden zusätzlich ausgewiesen. Es gilt R = E + W + M.</p>"
    content += skeleton(
        "sa-quality",
        [
            "Verfahren",
            "Teilnehmer-Schriftart",
            "R",
            "Exakte Feldtreffer E",
            "Vorhanden, abweichend W",
            "Fehlend / nicht nutzbar M",
            "Davon vollständig fehlender Endwert",
            "Davon vorhanden, aber nicht nutzbar",
            "Exact Recall E/R",
            "Field Coverage (R−M)/R",
            "Ø Levenshtein vorhandener Feldwerte",
            "Zuordnung unklar (zusätzlich)",
        ],
    )
    content += "<p>Fehlende Teilnehmer behalten alle erwarteten Feldbeiträge in ihrer GT-Gruppe. M umfasst fehlende/leer ausgegebene Werte und vorhandene, aber ungültige ID-Platzhalter; diese werden im Zähler kenntlich gemacht. Die bedingte Levenshtein-Ähnlichkeit nutzt vorhandene Felder D einschließlich abweichender Werte, niemals fehlende Werte. D=0: nicht definiert.</p>"
    content += '<p class="sa-legend"><span><i style="background:#23876b"></i>E/R exakt</span><span><i style="background:#e3a138"></i>W/R abweichend</span><span><i style="background:#bb4651"></i>M/R fehlend/nicht nutzbar</span>Gleich lange Balken zeigen relative Raten; R und absolute Zähler stehen daneben.</p>'
    content += '<div class="scroll"><svg class="sa-chart" id="sa-quality-chart" role="img" aria-label="Relative Feldkorrektheit, Abweichungen und Fehlwerte je Verfahren und Schriftart"></svg></div></section>'
    content += '<section class="hero"><h2>Absolute Fehler, Fehlerraten und Fehleranteile</h2><p>Fehlerrate: Fehler innerhalb der jeweiligen Gruppe geteilt durch deren R. Fehleranteil: Gruppenfehler geteilt durch alle Fehler desselben Verfahrens im Dokument-/Feldfilterumfang, einschließlich g und unklassifiziert. Der Schriftartfilter verkleinert diesen Anteilsnenner nicht. Große Gruppen können mehr Fehler verursachen und dennoch eine niedrigere Fehlerrate besitzen.</p>'
    content += skeleton(
        "sa-errors",
        [
            "Verfahren",
            "Schriftart",
            "W",
            "M",
            "W+M",
            "Falschrate W/R",
            "Fehlrate M/R",
            "Gesamtfehlerrate (W+M)/R",
            "Anteil aller abweichenden Werte",
            "Anteil aller fehlenden Werte",
            "Anteil aller Referenzfeldfehler",
        ],
    )
    content += '<div class="scroll"><svg class="sa-chart" id="sa-error-chart" role="img" aria-label="Anteil aller Referenzfeldfehler eines Verfahrens nach Schriftart"></svg></div></section>'
    content += '<section class="hero"><h2>Dokumentverfügbarkeit und methodische Grenzen</h2>'
    content += "<p>Die bisherige Referenzbewertung enthält weiterhin alle ungeprüften Fälle. Die zusätzliche Dokumentbewertung berücksichtigt ausschließlich unabhängig geprüfte, lesbare und nach bestehender Normalisierung referenzgleiche Originalwerte. Lesbare Referenzkonflikte bleiben separat. Eine selektive Prüfung einfacher Felder ergibt keinen korrigierten Gesamtscore und keinen repräsentativen Handschriftvergleich.</p>"
    content += skeleton(
        "sa-availability",
        [
            "Schriftart",
            "Unabhängig geprüft",
            "Lesbar und referenzgleich R_doc",
            "Lesbare Referenzkonflikte",
            *AVAILABILITY.values(),
        ],
    )
    content += "<p>Die Verfügbarkeitszahlen beziehen sich auf die ursprünglichen Referenzfelder im aktuellen Dokument-/Feldumfang, auch bei gewählter Dokumentbewertung. Fehlende Modellwerte oder OCR-Beobachtungen beweisen keine leere Originalzelle.</p>"
    content += "<p>Dokumentfilter verwenden den eingefrorenen Kursumfang oder unabhängige Referenzlokalisierungen. Bei genau einem PDF je Kurs ist die Zuordnung kursbezogen, kein Beweis der Anwesenheit jeder Person im Original. Bei mehreren PDFs ohne unabhängige Lokalisierung bleiben sämtliche Referenzfelder unter „PDF-Zuordnung ungeprüft“ erhalten; sie werden nicht auf einzelne PDFs dupliziert. Ausgabeseiten bestimmen keinen Referenznenner.</p>"
    content += "<p>Ungepaarte Zusatzausgaben besitzen keine GT-Schriftart. Sie werden keiner der vier Gruppen zugeteilt und bleiben vollständig in globaler Precision/F1 sowie im bestehenden Audit erhalten. Gepaart gegen ausdrücklich leere GT ausgegebene Werte bleiben dort Zusatzfehler, gehören aber nicht zum Nenner R dieser Textfeldanalyse.</p></section>"
    content += '<section class="hero"><h2>Einzelfelder und bestehende Bewertung</h2><p>Sichtbare Referenzfeldfälle: <span id="sa-detail-count"></span>. Auch nicht bewertbare GT-Felder können in dieser Detailtabelle stehen; R umfasst ausschließlich die bewertbaren nichtleeren Referenzen. Originalwert, Status und Ähnlichkeit stammen aus dem bestehenden Feld-Audit.</p><details><summary>Ground Truth und extrahierte Originalwerte anzeigen</summary><div class="scroll"><table><thead><tr>'
    headings = [
        "Verfahren",
        "Referenzdokument / Kurs",
        "Referenzperson / Zeile",
        "Feld",
        "Schriftart (Teilnehmer)",
        "Ground Truth",
        "Extrahierter Originalwert",
        "Status",
        "Levenshtein-Ähnlichkeit",
        "Dokumentverfügbarkeit",
        "Original-PDF / Ausgabeseite",
    ]
    content += "".join(f"<th>{esc(h)}</th>" for h in headings) + "</tr></thead><tbody>"
    for r in payload["details"]:
        attrs = dict(
            method=r["candidate"],
            document=r["reference_document_group"],
            field=r["field"],
            style=r["gt_style"],
            eligible=str(r["document_eligible"]).lower(),
        )
        content += "<tr data-sa-case " + " ".join(f'data-{k}="{esc(v)}"' for k, v in attrs.items()) + ">"
        values = [
            r["candidate"],
            payload["documents"][r["reference_document_group"]]["label"],
            str(r.get("participant_label") or "") + " · " + str(r["reference_row"]),
            LABELS[r["field"]],
            payload["styles"][r["gt_style"]],
            r.get("reference_value"),
            r.get("original_prediction_value"),
            r.get("evaluation_label"),
            detected_percent(
                r.get("similarity_percent") / 100 if r.get("similarity_percent") is not None else None
            ),
            AVAILABILITY.get(r["document_availability"], "Nicht bewertbare Referenz"),
        ]
        content += "".join(f"<td>{esc(v)}</td>" for v in values)
        content += (
            "<td>"
            + " · ".join(
                f'<a href="{esc(p["href"])}">{esc(p["label"])}</a>' for p in r.get("original_links", [])
            )
            + "</td></tr>"
        )
    content += '</tbody></table></div></details><p><a href="report.html#audit">Vollständiger Feld-/Teilnehmeraudit einschließlich Zusätzen und Ausschlüssen</a></p></section></main>'
    ui = {k: v for k, v in payload.items() if k not in ("details", "checks")}
    ui.update(field_labels=LABELS, availability=AVAILABILITY)
    content += (
        '<script type="application/json" id="schriftanalyse-data">'
        + json.dumps(ui, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>"
    )
    target = output / "handschrift_maschinenschrift.html"
    target.write_text(
        document("Handschrift vs. Maschinenschrift", content, script_source=SCRIPT), encoding="utf-8"
    )
    exports = []
    for basis, docs in payload["views"].items():
        for doc, fields in docs.items():
            for field, view in fields.items():
                for row in view["comparisons"]:
                    exports.append(dict(basis=basis, document_group=doc, field_filter=field, **row))
    write_csv(
        folder / "schriftart_analysis.csv",
        [
            {k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for k, v in r.items()}
            for r in exports
        ],
    )
    for name in (
        "report.html",
        "standard_report.html",
        "missing_fields.html",
        "validity.html",
        "extraction_errors.html",
    ):
        path = output / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if 'href="handschrift_maschinenschrift.html"' not in text:
                text = text.replace(
                    "</h1>",
                    '</h1><p><a href="handschrift_maschinenschrift.html"><strong>Handschrift vs. Maschinenschrift</strong></a></p>',
                    1,
                )
                path.write_text(text, encoding="utf-8")
    return target
