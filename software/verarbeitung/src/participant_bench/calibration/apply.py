"""Apply frozen local extraction and review gates to new PDFs without loading reference labels."""

import html
import uuid
from collections import Counter
from pathlib import Path

from ..config import Config
from ..io import digest, read_json, read_jsonl, write_csv, write_json
from ..runner import run
from ..schema import TEXT_FIELDS, PageResult
from .confidence import decide
from .experiment import VERSION, pipeline_fingerprint
from .metrics import field_score


def apply_frozen(experiment: Path, inputs: Path, output: Path | None = None) -> Path:
    frozen = read_json(experiment / "frozen.json")
    seal = frozen.pop("seal")
    if digest(frozen) != seal or frozen["version"] != VERSION:
        raise ValueError("Eingefrorene Auswahl verändert")
    config = Config.model_validate(frozen["config"])
    if any(spec.backend != "local" for spec in config.models.values()):
        raise ValueError("OCR-Anwendung ist ausschließlich lokal")
    if pipeline_fingerprint(config) != frozen["pipeline"]:
        raise ValueError("OCR-Engine, Modelle oder Implementierung seit Kalibrierung verändert")
    output = output or Path("runs") / ("a-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    config.output_dir = str(output / "r")
    folder, _ = run(config, inputs, offline=True)
    method = config.methods[0]
    decisions = []
    for record in read_jsonl(folder / method / "extractions.jsonl"):
        page = PageResult.model_validate(record)
        raw_path = folder / method / f"raw-{page.page_id}.json"
        data = read_json(raw_path).get("ocr", {}) if raw_path.exists() else {}
        for index, person in enumerate(page.participants):
            for name in TEXT_FIELDS:
                field = getattr(person, name)
                score = field_score(field, person, data)
                decisions.append(
                    dict(
                        document_id=page.document_id,
                        page_number=page.page_number,
                        prediction_index=index,
                        field=name,
                        value=field.value,
                        raw_score=score,
                        bbox=field.bbox.model_dump() if field.bbox else None,
                        **decide(frozen["policy"][name], score, field.value is not None),
                    )
                )
    write_csv(output / "decisions.csv", decisions)
    counts = dict(Counter(row["decision"] for row in decisions))
    write_json(
        output / "application.json",
        dict(
            seal=seal,
            dataset_id=frozen["dataset_id"],
            quality_measured=False,
            source_run=str(folder.resolve()),
            field_decisions=counts,
            note="Keine Referenzlabels geladen; keine Qualitätsgarantie für neue Daten.",
        ),
    )
    source_link = (folder / "report.html").relative_to(output).as_posix()
    (output / "report.html").write_text(
        f'''<!doctype html><html lang="de"><meta charset="utf-8">
<h1>Lokale OCR mit eingefrorenen Prüfregeln</h1><p>{html.escape(str(counts))}</p>
<p>Auf diesen neuen Daten wurde keine Qualität gemessen. Leer/unbekannt und fehlende Scores verlangen Nachkontrolle.</p>
<p><a href="decisions.csv">Feldentscheidungen und Quellen</a> · <a href="{source_link}">Extraktionsbericht und Rohdaten</a></p></html>''',
        encoding="utf-8",
    )
    return output
