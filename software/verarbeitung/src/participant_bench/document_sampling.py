"""Optional random PDF subset shared by every method; originals and full PDF pages stay intact."""

import random
import secrets
from pathlib import Path

from .io import write_json


def make_sample(inputs, count, seed=None):
    documents = sorted({r["sha256"] for r in inputs if r["kind"] == "pdf"})
    if type(count) is not int or not 1 <= count <= len(documents):
        raise ValueError(f"Dokumentanzahl muss zwischen 1 und {len(documents)} liegen")
    seed = secrets.randbits(63) if seed is None else seed
    if type(seed) is not int or seed < 0:
        raise ValueError("Der Zufalls-Seed muss eine nichtnegative ganze Zahl sein")
    selected = sorted(random.Random(seed).sample(documents, count))
    return dict(
        version=1,
        count=count,
        available_documents=len(documents),
        seed=seed,
        selected_document_ids=selected,
        population=inputs,
    )


def selected_inputs(inputs, sample):
    """Verify the frozen pool and deterministic choice; keep aliases for existing ambiguity checks."""
    if not isinstance(sample, dict) or sample.get("population") != inputs:
        raise ValueError("PDF-Auswahl passt nicht mehr zu Eingabepfaden und Prüfsummen")
    expected = make_sample(inputs, sample.get("count"), sample.get("seed"))
    if sample != expected:
        raise ValueError("Gespeicherte PDF-Zufallsauswahl wurde verändert")
    ids = set(sample["selected_document_ids"])
    return [r for r in inputs if r["kind"] == "pdf" and r["sha256"] in ids]


def ask_count(available):
    while True:
        try:
            answer = input(f"Wie viele PDFs testen? [1–{available}, Enter = alle]: ").strip()
        except EOFError:
            raise ValueError(
                "Keine Eingabe verfügbar; --documents ANZAHL oder --all-documents angeben"
            ) from None
        if not answer or answer.lower() in ("alle", "all"):
            return None
        try:
            count = int(answer)
        except ValueError:
            count = 0
        if 1 <= count <= available:
            return count
        print(f"Bitte eine ganze Zahl von 1 bis {available} eingeben, oder Enter für alle PDFs.", flush=True)


def annotate_report(output, manifest):
    sample = manifest.get("document_sample")
    if sample is None:
        return
    from .roster_benchmark.detail_report import esc

    chosen = selected_inputs(sample["population"], sample)
    write_json(output / "document_sample.json", sample)
    names = ", ".join(Path(r["path"]).name for r in chosen)
    note = (
        f"<details data-document-sample><summary>Zufallsauswahl im Quelllauf: {sample['count']} von "
        f"{sample['available_documents']} PDFs · Seed {sample['seed']}</summary>"
        "<p>Alle Verfahren erhalten im Quelllauf dieselben vollständigen PDFs. Originaldateien bleiben unverändert. "
        "Die Anzahl zählt unterschiedliche PDF-Inhalte; identische Dateikopien werden gemeinsam behandelt.</p>"
        f'<p>{esc(names)}</p><p><a href="document_sample.json">Auswahlprotokoll mit Seed und Prüfsummen</a></p>'
        "<p>Diese Zufallsauswahl ist ein verkürzter Testlauf, keine nach Abhängigkeiten geprüfte Studienstichprobe. "
        "Bei mehreren PDFs derselben Schulung bleibt deren vollständige Kursreferenz im Nenner.</p></details>"
    )
    for name in ("report.html", "standard_report.html"):
        path = output / name
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "data-document-sample" not in text:
                path.write_text(text.replace("</h1>", "</h1>" + note, 1), encoding="utf-8")
