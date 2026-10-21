"""Recheck saved participant predictions without repeating OCR or participant inference."""

import copy
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from PIL import Image

from .io import file_hash, read_json, read_jsonl, write_json, write_jsonl
from .models import LocalModel, create_model, require_offline, validate_api_environment
from .progress import Progress
from .report import report
from .runner import aggregate_status, signature_details
from .schema import PageResult, SignatureLocations, SignatureResponse
from .signatures import LOCATION_SYSTEM, SIGNATURE_PROMPT_VERSION, SIGNATURE_SYSTEM


def recheck_run(source: Path, config, methods=None, output: Path | None = None, *, offline=False) -> Path:
    require_offline(config, offline, methods=["vlm"])
    validate_api_environment(config, methods=["vlm"])
    if "vlm" not in config.models:
        raise ValueError("Für die Signaturprüfung muss models.vlm konfiguriert sein")
    original_summary = read_json(source / "summary.json")
    methods = methods or list(original_summary)
    if any(method not in original_summary for method in methods):
        raise ValueError("Gewähltes Verfahren ist im Quelllauf nicht vorhanden")
    config.signature.backend = "vlm"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = output or source / "signature-review" / stamp
    output.mkdir(parents=True, exist_ok=False)
    progress = Progress(output / "progress.log")
    manifest = copy.deepcopy(read_json(source / "manifest.json"))
    for page in manifest["pages"]:
        original_image = source / "pages" / f"{page['page_id']}.png"
        if original_image.is_file():
            destination = output / "pages" / original_image.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original_image, destination)
            page["image"] = str(destination.resolve())
    write_json(output / "manifest.json", manifest)
    prompts = read_json(source / "prompts.json") if (source / "prompts.json").is_file() else {}
    prompts.update(signature_prompt_version=SIGNATURE_PROMPT_VERSION, signature_system=SIGNATURE_SYSTEM,
                   signature_location_system=LOCATION_SYSTEM,
                   signature_location_response_schema=SignatureLocations.model_json_schema(),
                   signature_response_schema=SignatureResponse.model_json_schema())
    write_json(output / "prompts.json", prompts)
    (output / "config.yaml").write_text(yaml.safe_dump(config.model_dump(), allow_unicode=True), encoding="utf-8")
    source_hashes = {method: file_hash(source / method / "extractions.jsonl") for method in methods}
    provenance = {
        "kind": "signature_recheck_only", "source_run": str(source.resolve()),
        "participant_source_sha256": source_hashes, "new_participant_inference": False,
        "signature_prompt_version": SIGNATURE_PROMPT_VERSION,
    }
    write_json(output / "signature_recheck.json", provenance)
    progress.log("Nur Unterschriften nachprüfen; vorhandene Teilnehmerdaten übernehmen")
    results, summary = {}, {}
    started = time.perf_counter()
    model = None
    try:
        model = create_model("vlm", config, progress=progress, local_class=LocalModel)
        provenance["signature_model_identity"] = model.identity
        write_json(output / "signature_recheck.json", provenance)
        load_seconds = time.perf_counter() - started
        for method in methods:
            pages = [PageResult.model_validate(row) for row in read_jsonl(source / method / "extractions.jsonl")]
            method_dir = output / method
            method_dir.mkdir(exist_ok=True)
            raw_records = []
            method_started = time.perf_counter()
            for page in pages:
                page.run_id = output.name
                page.calls, page.timings = 0, {}
                raw_path = source / method / f"raw-{page.page_id}.json"
                raw = read_json(raw_path) if raw_path.is_file() else {}
                if method == "vlm" and config.signature.use_ocr_positions and not raw.get("signature_ocr"):
                    for baseline in ("ocr_llm", "ocr_rules"):
                        baseline_path = source / baseline / f"raw-{page.page_id}.json"
                        if baseline_path.is_file():
                            raw["signature_ocr"] = read_json(baseline_path).get("ocr")
                            if raw["signature_ocr"]:
                                break
                if page.participants:
                    progress.log(f"{method}: PDF-Seite {page.page_number}, {len(page.participants)} Teilnehmerzeilen")
                    image_path = output / "pages" / f"{page.page_id}.png"
                    with Image.open(image_path) as source_image:
                        with source_image.convert("RGB") as image:
                            signature_details(page, raw, image, model, config, method_dir)
                raw.update(status=page.status, signature_recheck_source=str(raw_path.resolve()))
                write_json(method_dir / f"raw-{page.page_id}.json", raw)
                raw_records.append(raw)
            results[method] = pages
            write_jsonl(method_dir / "extractions.jsonl", [page.model_dump() for page in pages])
            write_jsonl(method_dir / "raw.jsonl", raw_records)
            summary[method] = {
                "status": aggregate_status(pages), "kind": "signature_recheck_only",
                "participant_source": str((source / method / "extractions.jsonl").resolve()),
                "signature_backend": "vlm", "model_backend": config.models["vlm"].backend, "selected_pages": len(pages),
                "signature_recheck_wall_seconds": time.perf_counter() - method_started,
                "signature_model_load_seconds": load_seconds if method == methods[0] else 0.0,
                "generation_calls": sum(page.calls for page in pages),
                "output_signature_fields": sum(len(page.participants) for page in pages),
                "output_unknown_signatures": sum(person.signature_present is None for page in pages for person in page.participants),
            }
        write_json(output / "signature_model_resources.json", model.resources())
    finally:
        if model:
            model.close()
    if any(file_hash(source / method / "extractions.jsonl") != source_hashes[method] for method in methods):
        raise ValueError("Vorhersagen des Quelllaufs wurden während der Nachprüfung verändert")
    write_json(output / "summary.json", summary)
    # Previous quality scores/cost measurements must not be attributed to the new signature decisions.
    report(output, summary, results, {}, manifest, {"kind": "signature_recheck_only"})
    progress.log(f"Signaturprüfung abgeschlossen: {output / 'report.html'}")
    return output
