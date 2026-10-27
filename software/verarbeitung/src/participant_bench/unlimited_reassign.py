"""Assign saved Unlimited-OCR cells without re-running OCR or altering the source run."""

import copy
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from .models import create_model
from .progress import Progress
from .report import report
from .schema import PageResult
from .unlimited_assignment import PROMPT_VERSION, SYSTEM, AssignmentResponse, assign_pages


def reassign_run(source: Path, config, output: Path | None = None):
    from .runner import aggregate_status

    llm = config.models.get("ocr_llm")
    if llm is None or llm.backend != "local":
        raise ValueError("Zuordnung verwendet ausschließlich ein lokales models.ocr_llm")
    pages_path = source / "unlimited_ocr/extractions.jsonl"
    pages = [PageResult.model_validate(row) for row in read_jsonl(pages_path)]
    raw_paths = [source / "unlimited_ocr" / f"raw-{page.page_id}.json" for page in pages]
    hashes = {str(path.relative_to(source)): file_hash(path) for path in [pages_path, *raw_paths]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = output or Path(config.output_dir) / stamp
    output.mkdir(parents=True, exist_ok=False)
    method_dir = output / "unlimited_ocr"
    method_dir.mkdir()
    manifest = copy.deepcopy(read_json(source / "manifest.json"))
    for page in pages:
        original = source / "pages" / f"{page.page_id}.png"
        if original.is_file():
            destination = output / "pages" / original.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(original, destination)
        raw = read_json(source / "unlimited_ocr" / f"raw-{page.page_id}.json")
        raw.pop("assignment", None)
        raw.pop("signature_checks", None)
        write_json(method_dir / f"raw-{page.page_id}.json", raw)
        page.run_id, page.participants, page.calls, page.timings = output.name, [], 0, {}
        page.error, page.review_notes = None, []
    write_json(output / "manifest.json", manifest)
    (output / "config.yaml").write_text(yaml.safe_dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    write_json(output / "prompts.json", dict(assignment_prompt_version=PROMPT_VERSION,
               assignment_system=SYSTEM, assignment_schema=AssignmentResponse.model_json_schema()))
    provenance = dict(kind="unlimited_assignment_only", source_run=str(source.resolve()),
                      source_sha256=hashes, new_ocr_inference=False, prompt_version=PROMPT_VERSION)
    write_json(output / "assignment_recheck.json", provenance)
    progress = Progress(output / "progress.log")
    progress.log("Gespeicherte Unlimited-OCR-Zellen lokal zuordnen; keine erneute OCR")

    def persist():
        write_jsonl(method_dir / "extractions.jsonl", [page.model_dump() for page in pages])

    started = time.perf_counter()
    resources = assign_pages(pages, method_dir, config, progress,
                             lambda: create_model("ocr_llm", config, progress=progress), persist)
    persist()
    write_jsonl(method_dir / "raw.jsonl", [read_json(method_dir / f"raw-{page.page_id}.json") for page in pages])
    write_json(method_dir / "resources.json", resources)
    if any(file_hash(source / name) != value for name, value in hashes.items()):
        raise ValueError("Quelllauf hat sich während der Zuordnung verändert")
    summary = {"unlimited_ocr": dict(
        kind="unlimited_assignment_only", status=aggregate_status(pages), output_kind="structured",
        selected_pages=len(pages), model_backend="local", assignment_backend="local_llm",
        assignment_wall_seconds=time.perf_counter() - started, new_ocr_inference=False,
        signature_backend="not_run", generation_calls=sum(page.calls for page in pages),
    )}
    write_json(output / "summary.json", summary)
    report(output, summary, {"unlimited_ocr": pages}, {}, manifest, {"kind": "unlimited_assignment_only"})
    progress.log(f"Zellzuordnung abgeschlossen: {output / 'report.html'}")
    return output
