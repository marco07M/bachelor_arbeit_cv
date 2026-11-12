"""Assign saved Unlimited-OCR cells without re-running OCR or altering the source run."""

import copy
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image

from .column_context import VERSION as COLUMN_CONTEXT_VERSION
from .column_context import image_boundaries
from .io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from .models import create_model
from .progress import Progress
from .report import report
from .schema import PageResult
from .unlimited_assignment import PROMPT_VERSION, assign_pages


def reassign_run(source: Path, config, output: Path | None = None, *, methods=None):
    from .runner import aggregate_status

    llm = config.models.get("ocr_llm")
    if llm is None or llm.backend != "local":
        raise ValueError("Zuordnung verwendet ausschließlich ein lokales models.ocr_llm")
    methods = methods or ["unlimited_ocr"]
    if not methods or len(set(methods)) != len(methods) or set(methods) - {"unlimited_ocr", "paddle_structure", "paddle_llm", "docling"}:
        raise ValueError("Nur gespeicherte Unlimited-, Paddle- oder Docling-Ergebnisse zuordnen")
    if config.main_comparison and "docling" in methods:
        raise ValueError("Docling verwendet deterministisches Mapping; kein nachträgliches LLM im Hauptvergleich")
    results, hashes = {}, {"manifest.json": file_hash(source / "manifest.json")}
    for method in methods:
        pages_path = source / method / "extractions.jsonl"
        results[method] = [PageResult.model_validate(row) for row in read_jsonl(pages_path)]
        paths = [pages_path, *(source / method / f"raw-{page.page_id}.json" for page in results[method])]
        hashes.update({str(path.relative_to(source)): file_hash(path) for path in paths})
        if method != "unlimited_ocr" and method not in config.structures:
            raise ValueError("structures-Konfiguration für das gewählte Verfahren fehlt")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = output or Path(config.output_dir) / stamp
    output.mkdir(parents=True, exist_ok=False)
    manifest = copy.deepcopy(read_json(source / "manifest.json"))
    geometry_seconds = {}
    for method, pages in results.items():
        geometry_started = time.perf_counter()
        method_dir = output / method
        method_dir.mkdir()
        for page in pages:
            original = source / "pages" / f"{page.page_id}.png"
            if original.is_file():
                destination = output / "pages" / original.name
                destination.parent.mkdir(exist_ok=True)
                shutil.copy2(original, destination)
            raw = read_json(source / method / f"raw-{page.page_id}.json")
            if method != "unlimited_ocr" and original.is_file():
                hashes[str(original.relative_to(source))] = file_hash(original)
                with Image.open(original) as image:
                    raw["structure"]["image_column_boundaries"] = image_boundaries(image)
            raw.pop("assignment", None)
            raw.pop("signature_checks", None)
            prior = {key: raw.pop(key) for key in ("document_name_order", "person_role_filter") if key in raw}
            if prior:
                raw["historical_postprocessing"] = prior  # Old states/indices do not describe a new assignment.
            write_json(method_dir / f"raw-{page.page_id}.json", raw)
            page.run_id, page.participants, page.calls, page.timings = output.name, [], 0, {}
            page.error, page.review_notes = None, []
        geometry_seconds[method] = time.perf_counter() - geometry_started
    write_json(output / "manifest.json", manifest)
    (output / "config.yaml").write_text(yaml.safe_dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    from .models import extraction_prompt_snapshot

    write_json(output / "prompts.json", extraction_prompt_snapshot())
    kind = "unlimited_assignment_only" if methods == ["unlimited_ocr"] else "structure_assignment_only"
    provenance = dict(kind=kind, methods=methods, source_run=str(source.resolve()),
                      column_context_version=COLUMN_CONTEXT_VERSION,
                      geometry_preparation_seconds=geometry_seconds,
                      source_sha256=hashes, new_ocr_inference=False, prompt_version=PROMPT_VERSION,
                      assignment_code_sha256={p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")})
    write_json(output / "assignment_recheck.json", provenance)
    progress = Progress(output / "progress.log")
    progress.log("Gespeicherte OCR-/Tabellenbelege lokal zuordnen; keine erneute OCR")
    summary = {}
    for method, pages in results.items():
        method_dir = output / method

        def persist():
            write_jsonl(method_dir / "extractions.jsonl", [page.model_dump() for page in pages])

        started = time.perf_counter()
        resources = assign_pages(pages, method_dir, config, progress,
                                 lambda: create_model("ocr_llm", config, progress=progress), persist, method=method)
        persist()
        write_jsonl(method_dir / "raw.jsonl", [read_json(method_dir / f"raw-{page.page_id}.json") for page in pages])
        write_json(method_dir / "resources.json", resources)
        summary[method] = dict(
            kind=kind, status=aggregate_status(pages), output_kind="structured",
            selected_pages=len(pages), model_backend="local", assignment_backend="local_llm",
            assignment_wall_seconds=time.perf_counter() - started, new_ocr_inference=False,
            signature_backend="not_run", generation_calls=sum(page.calls for page in pages),
            structure_backend=("PP-StructureV3" if method == "paddle_structure" else
                               "TableFormer" if method == "docling" else None),
        )
    if any(file_hash(source / name) != value for name, value in hashes.items()):
        raise ValueError("Quelllauf hat sich während der Zuordnung verändert")
    write_json(output / "summary.json", summary)
    report(output, summary, results, {}, manifest, {"kind": kind})
    progress.log(f"Zellzuordnung abgeschlossen: {output / 'report.html'}")
    return output
