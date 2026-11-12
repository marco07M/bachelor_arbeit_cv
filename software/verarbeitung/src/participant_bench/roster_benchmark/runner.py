"""Reuse the extraction runner sequentially, then compare frozen reference values in a separate step."""

from pathlib import Path

from ..config import Config
from ..config import load_config as load_extraction_config
from ..io import file_hash
from ..models import require_offline
from ..runner import run as extract
from .config import reference_path, resolve
from .evaluation import evaluate_run, identify_course
from .references import read_reference


def preflight(config, base, input_override=None, reference_override=None):
    folder = input_override.resolve() if input_override else resolve(base, config.input_dir)
    if not folder.is_dir():
        raise ValueError("PDF-Eingabeordner fehlt")
    pdfs = sorted(path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdfs:
        raise ValueError("Keine PDFs im Eingabeordner; PDFs in testframework/eingabe_pdfs ablegen")
    reference = reference_path(config, base, reference_override)
    reference_hash = file_hash(reference)
    data = read_reference(reference, config.reference)
    if file_hash(reference) != reference_hash:
        raise ValueError("Referenzdatei wurde während des Einlesens geändert")
    known = {person.class_id for person in data.people}
    input_courses = {identify_course(str(path), known) for path in pdfs}
    common = known & input_courses
    if not common:
        raise ValueError("Keine gemeinsamen Schulungs-IDs: PDF-Dateiname muss zur Class ID der Referenz passen")
    overview = dict(input_pdfs=len(pdfs), reference_rows=len(data.people), reference_courses=len(known),
                    courses_compared=len(common), pdf_courses_without_reference=len(input_courses - known),
                    reference_courses_outside_input=len(known - input_courses),
                    merged_identical_reference_rows=sum(row["copies"] - 1 for row in data.duplicate_rows))
    return folder, reference, (data, reference_hash), overview


def run_benchmark(config, base: Path, *, input_override=None, reference_override=None, methods=None, resume=None,
                  allow_api=False, manifest_path=None):
    folder, reference, frozen, overview = preflight(config, base, input_override, reference_override)
    extraction = load_extraction_config(resolve(base, config.extraction_config))
    if methods:
        extraction = Config.model_validate(dict(extraction.model_dump(), methods=methods))
    extraction.pdf.recursive = True
    extraction.pdf.include_images = False
    if not config.signature_detail_checks:
        extraction.signature.backend = "opencv"
    output_root = resolve(base, config.output_dir)
    if output_root.is_relative_to(folder) or Path(extraction.output_dir).resolve().is_relative_to(folder):
        raise ValueError("Eingabe und Ergebnisordner müssen getrennt liegen")
    require_offline(extraction, not allow_api)
    print(f"Testframework: {overview['input_pdfs']} PDFs, {overview['courses_compared']} Schulungen im Referenzabgleich", flush=True)
    print("Modelle verarbeiten PDFs/Seiten nacheinander. Referenzwerte werden nicht an die Extraktion übergeben.", flush=True)
    # Only model configuration and PDF directory enter the existing inference runner.
    options = dict(resume=resume, offline=not allow_api)
    if manifest_path is not None:
        options["manifest_path"] = manifest_path.resolve()
    source, _ = extract(extraction, folder, **options)
    print("Extraktion abgeschlossen; Schulungen gruppieren und Teilnehmer global zuordnen ...", flush=True)
    return evaluate_run(source, reference, config, output_root, methods, frozen_reference=frozen)
