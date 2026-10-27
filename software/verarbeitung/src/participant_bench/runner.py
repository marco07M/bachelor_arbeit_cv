import copy
import gc
import importlib.metadata
import json
import threading
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psutil
import yaml
from PIL import Image

from .doctor import environment
from .evaluation import evaluate_groups
from .io import digest, file_hash, read_json, read_jsonl, write_csv, write_json, write_jsonl
from .models import (
    METHOD_INSTRUCTIONS,
    OCR_SYSTEM,
    PROMPT_VERSION,
    SYSTEM,
    VLM_SYSTEM,
    LocalModel,
    Unavailable,
    create_model,
    model_identity,
    require_offline,
    validate_model_environment,
)
from .ocr import OCR
from .ocr_layout import readable_text
from .pdf import prepare, run_identity, validate_manifest
from .progress import Progress
from .report import cost_scenario, report
from .rules import attach_signatures, extract_rules
from .schema import (
    GroundTruthPage,
    ModelResponse,
    OCRPageResponse,
    PageResult,
    SignatureLocations,
    SignatureResponse,
    VisualPageResponse,
)
from .signatures import LOCATION_SYSTEM, SIGNATURE_PROMPT_VERSION, SIGNATURE_SYSTEM, inspect_signatures


class MemoryMonitor:
    def __init__(self):
        self.peak = 0
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        process = psutil.Process()
        while not self.stop_event.is_set():
            try:
                processes = [process] + process.children(recursive=True)
                self.peak = max(self.peak, sum(p.memory_info().rss for p in processes if p.is_running()))
            except psutil.Error:
                pass
            self.stop_event.wait(0.1)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        self.thread.join()


def aggregate_status(pages):
    counts = Counter(p.status for p in pages)
    if not pages:
        return "partial"
    if counts["unavailable"] == len(pages):
        return "unavailable"
    if counts["failed"] == len(pages):
        return "failed"
    if counts["success"] == len(pages):
        return "success"
    return "partial"


def signature_details(result, raw, image, model, config, method_dir):
    started, previous_calls = time.perf_counter(), model.calls
    try:
        records, elapsed, calls = inspect_signatures(
            result.participants, image, model, config, method_dir, result.page_id,
            ocr_data=raw.get("ocr") or raw.get("signature_ocr"),
        )
    except Exception as exc:
        raw["signature_stage_error"] = f"{type(exc).__name__}: {exc}"
        result.calls += max(0, model.calls - previous_calls)
        result.timings["signature_seconds"] = result.timings.get("signature_seconds", 0.0) + time.perf_counter() - started
        result.review_notes.append("Zusätzliche Signaturprüfung fehlgeschlagen; Teilnehmerdaten bleiben erhalten")
        if result.status == "success":
            result.status = "partial"
        return
    raw["signature_checks"] = records
    result.calls += calls
    result.timings["signature_seconds"] = result.timings.get("signature_seconds", 0.0) + elapsed
    if result.status == "success" and (
        any(record.get("error") for record in records)
        or any(record.get("observation", {}).get("signature_present") is None
               for record in records if not record.get("skipped_known"))
        or any(person.signature_present is None for person in result.participants)
    ):
        result.status = "partial"


def load_truth(path, manifest, split, scope):
    pages = [GroundTruthPage.model_validate_json(json.dumps(row)) for row in read_jsonl(path)]
    keys = [(p.document_id, p.page_number) for p in pages]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate Ground Truth document/page")
    known_docs = {p["document_id"] for p in manifest["pages"]} | {
        i["sha256"] for i in manifest["inputs"] if i["kind"] == "pdf"
    }
    if any(p.document_id not in known_docs for p in pages):
        raise ValueError("Ground Truth document not present in input inventory")
    manifest_pages = {(p["document_id"], p["page_number"]): p for p in manifest["pages"]}
    readable_docs = {p["document_id"] for p in manifest["pages"]}
    for page in pages:
        key = (page.document_id, page.page_number)
        if page.document_id in readable_docs and key not in manifest_pages:
            raise ValueError("Ground Truth references nonexistent PDF page")
        annotation = manifest_pages.get(key, {})
        if annotation.get("split") is not None and annotation["split"] != page.split:
            raise ValueError("Ground Truth split disagrees with frozen page manifest")
    groups = {}
    docs = {}
    for page in pages:
        groups.setdefault(page.dependency_group, set()).add(page.split)
        docs.setdefault(page.document_id, set()).add(page.split)
    if any(len(s) > 1 for s in list(groups.values()) + list(docs.values())):
        raise ValueError("Document/dependency group crosses development/test boundary")
    selected = {(p["document_id"], p["page_number"]) for p in manifest["pages"] if p["include"]}
    return [
        p
        for p in pages
        if (split == "all" or p.split == split)
        and (scope != "curated" or (p.document_id, p.page_number) in selected)
    ]


def run(config, folder, manifest_path=None, truth_path=None, scope="end-to-end", split="all", resume=None, *, offline=False):
    require_offline(config, offline)
    validate_model_environment(config)
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(resume) if resume else Path(config.output_dir) / stamp
    if not resume:
        output.mkdir(parents=True, exist_ok=False)
    elif not (output / "identity.json").is_file():
        raise ValueError("Resume folder has no saved identity")
    progress = Progress(output / "progress.log")
    progress.log(f"{'Lauf fortsetzen' if resume else 'Lauf starten'}: {output.name}; Verfahren: {', '.join(config.methods)}")
    progress.log(f"Eingabe: {folder.resolve()}; Ergebnisse: {output.resolve()}")
    ocr, ocr_error = None, None
    if config.pdf.auto_orient or any(method in ("ocr_rules", "ocr_llm") for method in config.methods):
        try:
            with progress.activity("Lokale OCR für Ausrichtung bzw. Textextraktion initialisieren"):
                ocr = OCR(config)
        except (OSError, RuntimeError) as exc:
            ocr_error = str(exc)
            progress.log(f"OCR nicht verfügbar: {exc}; VLM kann weiterhin Seitenbilder verarbeiten")
    else:
        progress.log("VLM-Direktextraktion: alle Eingabeseiten ohne OCR-Voranalyse verarbeiten")
    if resume and manifest_path is None:
        manifest_path = Path(read_json(output / "identity.json")["source_manifest"])
    if manifest_path:
        with progress.activity("Vorhandenes Seitenmanifest, Eingaben und Bilder prüfen"):
            manifest = validate_manifest(manifest_path, folder, config, progress=progress)
    else:
        manifest = prepare(folder, config, output / "prepared", ocr, progress=progress)
        manifest_path = output / "prepared/manifest.json"
    progress.log(f"Eingabeseiten: {len(manifest['pages'])}; "
                 f"{sum(p['include'] for p in manifest['pages'])} zur Extraktion enthalten")
    if scope == "curated" and not manifest.get("curated"):
        raise ValueError("Curated evaluation requires manually reviewed manifest with curated=true")
    if split != "all" and any(p.get("split") not in ("development", "validation", "test") for p in manifest["pages"]):
        raise ValueError("--split requires development/validation/test annotations on every manifest page")
    progress.log("Modellverfügbarkeit und Laufidentität prüfen")
    identities = {}
    for method in config.methods:
        if method in config.models:
            try:
                identities[method] = model_identity(config.models[method])
            except Unavailable as exc:
                identities[method] = {"unavailable": str(exc)}
    unlimited_spec = config.models.get("unlimited_ocr")
    if "unlimited_ocr" in config.methods and unlimited_spec and unlimited_spec.options.get("extraction") == "llm":
        try:
            identities["unlimited_assignment_llm"] = model_identity(config.models["ocr_llm"])
        except Unavailable as exc:
            identities["unlimited_assignment_llm"] = {"unavailable": str(exc)}
    if config.signature.backend in ("local_vlm", "vlm") and "vlm" in config.models:
        try:
            identities["signature_vlm"] = model_identity(config.models["vlm"])
        except Unavailable as exc:
            identities["signature_vlm"] = {"unavailable": str(exc)}
    code = {str(p.name): file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    identity = digest(
        {
            "input_config": run_identity(config, manifest, identities),
            "code": code,
            "prompt": PROMPT_VERSION,
            "lock": file_hash(Path("uv.lock")),
            "ocr": ocr.identity if ocr else ocr_error,
            "scope": scope,
            "split": split,
            "ground_truth": file_hash(truth_path) if truth_path else None,
            "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        }
    )
    if resume and read_json(output / "identity.json")["fingerprint"] != identity:
        raise ValueError("Resume rejected: inputs, config, code, environment, model, OCR or truth changed")
    run_id = output.name
    write_json(
        output / "identity.json",
        {
            "fingerprint": identity,
            "source_manifest": str(manifest_path.resolve()),
            "models": identities,
            "prompt_version": PROMPT_VERSION,
            "scope": scope,
            "split": split,
        },
    )
    (output / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), allow_unicode=True), encoding="utf-8"
    )
    with progress.activity("Hardware, CUDA und Paketversionen erfassen"):
        write_json(output / "environment.json", environment(config))
    manifest_snapshot = copy.deepcopy(manifest)
    manifest_snapshot["source_manifest"] = str(manifest_path.resolve())
    for page in manifest_snapshot["pages"]:
        if page["status"] == "ready":
            page["image"] = str((manifest_path.parent / page["image"]).resolve())
    write_json(output / "manifest.json", manifest_snapshot)
    write_json(
        output / "prompts.json",
        {
            "version": PROMPT_VERSION,
            "system": SYSTEM,
            "ocr_system": OCR_SYSTEM,
            "vlm_system": VLM_SYSTEM,
            "method_instructions": METHOD_INSTRUCTIONS,
            "response_schema": ModelResponse.model_json_schema(),
            "ocr_response_schema": OCRPageResponse.model_json_schema(),
            "vlm_response_schema": VisualPageResponse.model_json_schema(),
            "signature_prompt_version": SIGNATURE_PROMPT_VERSION,
            "signature_system": SIGNATURE_SYSTEM,
            "signature_location_system": LOCATION_SYSTEM,
            "signature_location_response_schema": SignatureLocations.model_json_schema(),
            "signature_response_schema": SignatureResponse.model_json_schema(),
        },
    )
    if "unlimited_ocr" in config.methods and unlimited_spec and unlimited_spec.options.get("extraction") == "llm":
        from .unlimited_assignment import PROMPT_VERSION as assignment_version
        from .unlimited_assignment import SYSTEM as assignment_system
        from .unlimited_assignment import AssignmentResponse

        prompts = read_json(output / "prompts.json")
        prompts.update(assignment_prompt_version=assignment_version, assignment_system=assignment_system,
                       assignment_schema=AssignmentResponse.model_json_schema())
        write_json(output / "prompts.json", prompts)
    page_dir = output / "pages"
    page_dir.mkdir(exist_ok=True)
    # Apply only explicit manual correction to the already metadata/OSD-oriented image.
    prepared_pages = []
    image_preparation_start = time.perf_counter()
    for index, original in enumerate(manifest["pages"], 1):
        progress.log(f"Laufbilder vorbereiten [{index}/{len(manifest['pages'])}]: "
                     f"{Path(original['source_path']).name}, PDF-Seite {original['page_number']}")
        page = dict(original)
        if split != "all" and page["split"] != split:
            page["include"] = False
        if page["status"] == "ready":
            source = manifest_path.parent / page["image"]
            with Image.open(source) as image:
                transformed = image.rotate(-page.get("curation_rotation_clockwise", 0), expand=True)
                target = page_dir / f"{page['page_id']}.png"
                transformed.save(target)
                transformed.close()
            page["run_image"] = str(target)
            page["run_image_sha256"] = file_hash(target)
        prepared_pages.append(page)
    write_json(output / "effective_pages.json", prepared_pages)
    image_preparation_seconds = time.perf_counter() - image_preparation_start
    truths = load_truth(truth_path, manifest, split, scope) if truth_path else None
    results, summaries, errors, metrics = {}, {}, list(manifest["errors"]), {}
    if resume and (output / "errors.jsonl").is_file():
        errors.extend(read_jsonl(output / "errors.jsonl"))
    for method_index, method in enumerate(config.methods, 1):
        selected_pages = [p for p in prepared_pages if p["include"]]
        progress.log(f"Verfahren [{method_index}/{len(config.methods)}]: {method}; {len(selected_pages)} Seiten")
        method_dir = output / method
        method_dir.mkdir(exist_ok=True)
        checkpoint_path = method_dir / "checkpoint.jsonl"
        history_path = method_dir / "attempts.jsonl"
        history = (
            [PageResult.model_validate_json(json.dumps(r)) for r in read_jsonl(history_path)]
            if resume and history_path.is_file()
            else []
        )
        cached = {}
        if resume and checkpoint_path.is_file():
            cached = {
                p.page_id: p
                for p in [PageResult.model_validate_json(json.dumps(r)) for r in read_jsonl(checkpoint_path)]
                if p.status == "success"
            }
        page_results, raw_records = [], []
        unavailable = ocr_error if method in ("ocr_rules", "ocr_llm") else None
        model, resource = None, {"load_failed": False}
        prior_resource = (
            read_json(method_dir / "resources.json")
            if resume and (method_dir / "resources.json").is_file()
            else {}
        )
        method_start = time.perf_counter()
        with MemoryMonitor() as memory:
            try:
                needs_model = method != "ocr_rules" and any(
                    p["include"] and p["status"] == "ready" and p["page_id"] not in cached
                    for p in prepared_pages
                )
                if needs_model and not unavailable:
                    if method not in config.models:
                        unavailable = "No model configuration for method"
                    else:
                        load_attempt_start = time.perf_counter()
                        try:
                            model = create_model(method, config, progress=progress, local_class=LocalModel)
                        except Unavailable as exc:
                            unavailable = str(exc)
                        except Exception as exc:
                            unavailable = f"Model load failed: {type(exc).__name__}: {exc}"
                            resource["load_failed"] = True
                        resource["load_attempt_wall_seconds"] = time.perf_counter() - load_attempt_start
                elif method != "ocr_rules" and not needs_model:
                    progress.log(f"{method}: kein Modellladen nötig; keine offenen verarbeitbaren Seiten")
                if unavailable:
                    progress.log(f"{method}: nicht verfügbar: {unavailable}")
                for page_index, page in enumerate(selected_pages, 1):
                    label = (f"{method} [{page_index}/{len(selected_pages)}]: "
                             f"{Path(page['source_path']).name}, PDF-Seite {page['page_number']}")
                    progress.log(label + "; Verarbeitung starten")
                    if page["page_id"] in cached:
                        page_results.append(cached[page["page_id"]])
                        progress.log(label + "; erfolgreiches Ergebnis aus vorherigem Lauf übernommen")
                        continue
                    result = PageResult(
                        run_id=run_id,
                        document_id=page["document_id"],
                        page_number=page["page_number"],
                        page_id=page["page_id"],
                        method_id=method,
                        status="failed",
                        output_kind=("ocr_text" if method == "unlimited_ocr" and
                                     config.models[method].options.get("extraction", "none") == "none" else "structured"),
                    )
                    raw = {"page_id": page["page_id"], "method_id": method}
                    page_start = time.perf_counter()
                    try:
                        if page["status"] != "ready":
                            raise ValueError("Page rendering failed: " + " | ".join(page["reasons"]))
                        if unavailable:
                            result.status = "failed" if resource.get("load_failed") else "unavailable"
                            result.error = unavailable
                        else:
                            with Image.open(page["run_image"]) as loaded:
                                image = loaded.convert("RGB")
                            try:
                                if method in ("ocr_rules", "ocr_llm"):
                                    lookup_start = time.perf_counter()
                                    with progress.activity("OCR für die Extraktion"):
                                        options = {} if config.ocr.source == "ocr" else {
                                            "embedded_words": page.get("embedded_words"),
                                            "rotation_clockwise": (page.get("additional_rotation_clockwise", 0) + page.get("curation_rotation_clockwise", 0)) % 360,
                                        }
                                        data = ocr.recognize(image, page["run_image_sha256"], **options)
                                    progress.log("OCR aus Cache übernommen" if data["cache_hit"] else "OCR neu berechnet")
                                    result.timings["ocr_lookup_wall_seconds"] = (
                                        time.perf_counter() - lookup_start
                                    )
                                    result.timings["ocr_charged_seconds"] = data["elapsed_seconds"]
                                    result.timings["ocr_cache_hit"] = float(data["cache_hit"])
                                    raw["ocr"] = data
                                if method == "unlimited_ocr":
                                    participants, responses, status, elapsed = model.extract(image)
                                    response = responses[0]
                                    raw["responses"] = [{key: response[key] for key in
                                        ("raw_response", "parse_status", "output_kind", "output_tokens", "output_budget_reached")}]
                                    raw["unlimited_ocr"] = {key: value for key, value in response.items() if key != "raw_response"}
                                    result.participants, result.status = participants, status
                                    result.output_kind = response["output_kind"]
                                    result.page_text = response["plain_text"]
                                    result.parse_status = response["parse_status"]
                                    result.review_notes.extend(response.get("review_notes", []))
                                    result.calls = 1
                                    result.timings["model_extraction_seconds"] = elapsed
                                    result.timings.update(response.get("timings", {}))
                                    if response.get("output_budget_reached"):
                                        result.review_notes.append("OCR-Ausgabe am Tokenlimit abgeschnitten; Rohtext erhalten")
                                elif method == "ocr_rules":
                                    progress.log("Tabellenzeilen, Felder und Unterschriftsfelder mit Regeln auswerten")
                                    participants, notes, timings = extract_rules(image, data, config)
                                    result.participants, result.review_notes = participants, notes
                                    result.timings.update(timings)
                                    result.parse_status = "valid"
                                    result.status = "partial" if notes and not participants else "success"
                                else:
                                    participants, responses, status, elapsed = model.extract(
                                        image, data if method == "ocr_llm" else None
                                    )
                                    raw["responses"] = responses
                                    result.calls = len(responses)
                                    result.participants, result.status = participants, status
                                    result.review_notes.extend(
                                        note for response in responses for note in response.get("review_notes", [])
                                    )
                                    texts = [r["page_text"] for r in responses if r.get("page_text") is not None]
                                    result.page_text = "\n\n".join(texts) if texts else None
                                    result.text_fallback = any(r.get("text_fallback", False) for r in responses)
                                    if result.text_fallback:
                                        result.review_notes.append(
                                            "Keine Teilnehmer in mindestens einem Bildabschnitt erkannt; "
                                            "Seitentext als Fallback erhalten. Manuell prüfen."
                                        )
                                    response_errors = [r["error"] for r in responses if r.get("error")]
                                    result.error = " | ".join(response_errors) if response_errors else None
                                    result.parse_status = (
                                        "invalid"
                                        if any(r["parse_status"] != "valid" for r in responses)
                                        else "valid"
                                    )
                                    if not any(r["parse_status"] == "invalid" for r in responses):
                                        result.parse_status = (
                                            "valid"
                                            if any(r["parse_status"] == "valid" for r in responses)
                                            else "not_attempted"
                                        )
                                    result.timings["model_extraction_seconds"] = elapsed
                                    if method == "ocr_llm":
                                        progress.log("Unterschriftsfelder anhand des Seitenbildes prüfen")
                                        result.timings["signature_seconds"] = attach_signatures(
                                            participants, image, data, config
                                        )
                                    else:
                                        result.review_notes.append(
                                            "Signaturpräsenz im Gesamtbild durch VLM beurteilt; "
                                            "zusätzliche Detailprüfung und Laufzeit separat protokolliert"
                                        )
                                        if config.signature.backend in ("local_vlm", "vlm") and participants:
                                            if ocr is not None and config.signature.use_ocr_positions:
                                                position_start = time.perf_counter()
                                                try:
                                                    raw["signature_ocr"] = ocr.recognize(image, page["run_image_sha256"])
                                                except Exception:
                                                    result.review_notes.append("OCR-Positionsbelege fehlen; VLM-Lokalisierung verwenden")
                                                lookup_elapsed = time.perf_counter() - position_start
                                                result.timings["signature_ocr_lookup_wall_seconds"] = lookup_elapsed
                                                result.timings["signature_seconds"] = raw.get("signature_ocr", {}).get("elapsed_seconds", lookup_elapsed)
                                            signature_details(result, raw, image, model, config, method_dir)
                            finally:
                                image.close()
                    except Exception as exc:
                        result.error = f"{type(exc).__name__}: {exc}"
                        result.status = "failed"
                    if method in ("ocr_rules", "ocr_llm") and not result.participants and "ocr" in raw:
                        result.page_text = readable_text(raw["ocr"])
                        result.text_fallback = True
                        result.review_notes.append(
                            "Keine Teilnehmer strukturiert erkannt; vorhandener OCR-Text als Fallback erhalten. "
                            "Manuell prüfen. OCR kann handschriftliche oder schlecht lesbare Inhalte übersehen."
                        )
                        progress.log(label + "; OCR-Text als Fallback gesichert")
                    if result.error:
                        progress.log(label + "; Fehler; Details in den lokalen Rohdaten")
                    result.timings["page_wall_seconds"] = time.perf_counter() - page_start
                    measured_stages = sum(
                        value
                        for key, value in result.timings.items()
                        if key
                        in (
                            "ocr_lookup_wall_seconds",
                            "structure_seconds",
                            "signature_seconds",
                            "model_extraction_seconds",
                        )
                    )
                    result.timings["page_overhead_seconds"] = max(
                        0.0, result.timings["page_wall_seconds"] - measured_stages
                    )
                    result = PageResult.model_validate_json(result.model_dump_json())
                    raw.update(parse_status=result.parse_status, status=result.status, error=result.error)
                    write_json(method_dir / f"raw-{page['page_id']}.json", raw)
                    attempt_number = 1 + sum(r.page_id == page["page_id"] for r in history)
                    write_json(method_dir / "attempts" / f"raw-{page['page_id']}-{attempt_number}.json", raw)
                    history.append(result)
                    write_jsonl(history_path, [r.model_dump() for r in history])
                    page_results.append(result)
                    write_jsonl(checkpoint_path, [r.model_dump() for r in page_results])
                    progress.log(
                        f"{label}; Status={result.status}, JSON={result.parse_status}, "
                        f"{len(result.participants)} Einträge, {result.timings['page_wall_seconds']:.1f}s; "
                        f"Ergebnis gesichert ({page_index / len(selected_pages):.0%})"
                    )
                    if result.error:
                        errors.append({"method": method, "page_id": page["page_id"], "reason": result.error})
                if model:
                    resource.update(model.resources())
            finally:
                if model:
                    with progress.activity(f"{method}: Modell entladen und GPU-Speicher freigeben"):
                        model.close()
                gc.collect()
            # OCR methods finish/unload their extraction model before loading the shared signature VLM.
            # No participant values or assignments are transferred between extraction methods.
            if method == "unlimited_ocr" and config.models[method].options.get("extraction") == "llm":
                from .unlimited_assignment import assign_pages

                def persist_assignment():
                    for result in page_results:
                        matching = [i for i, attempt in enumerate(history) if attempt.page_id == result.page_id]
                        if matching:
                            history[matching[-1]] = result
                    write_jsonl(history_path, [row.model_dump() for row in history])
                    write_jsonl(checkpoint_path, [row.model_dump() for row in page_results])

                assignment_resource = assign_pages(
                    page_results, method_dir, config, progress,
                    lambda: create_model("ocr_llm", config, progress=progress, local_class=LocalModel),
                    persist_assignment,
                )
                resource["assignment_model"] = assignment_resource
                for key in ("load_seconds", "load_attempt_wall_seconds", "warmup_seconds", "warmup_calls"):
                    resource[key] = resource.get(key, 0) + assignment_resource.get(key, 0)
                for key in ("peak_gpu_allocated_bytes", "peak_gpu_reserved_bytes"):
                    resource[key] = max(resource.get(key) or 0, assignment_resource.get(key) or 0)
                errors.extend(dict(method=method, page_id=page.page_id, reason=page.error)
                              for page in page_results if page.error)
            if method != "vlm" and config.signature.backend in ("local_vlm", "vlm"):
                pending = [page for page in page_results if page.participants and not
                           read_json(method_dir / f"raw-{page.page_id}.json").get("signature_checks")]
                signature_model = None
                signature_load_start = time.perf_counter()
                try:
                    if pending:
                        progress.log(f"{method}: separates VLM für Unterschriften initialisieren; "
                                     f"{len(pending)} Seiten mit Teilnehmenden")
                        signature_model = create_model("vlm", config, progress=progress, local_class=LocalModel)
                        resource["signature_load_attempt_wall_seconds"] = time.perf_counter() - signature_load_start
                    for result in pending:
                        page = next(page for page in selected_pages if page["page_id"] == result.page_id)
                        raw_path = method_dir / f"raw-{result.page_id}.json"
                        raw = read_json(raw_path)
                        detail_start = time.perf_counter()
                        try:
                            with Image.open(page["run_image"]) as source:
                                with source.convert("RGB") as image:
                                    signature_details(result, raw, image, signature_model, config, method_dir)
                        except Exception as exc:
                            raw["signature_stage_error"] = f"{type(exc).__name__}: {exc}"
                            result.review_notes.append("Signaturprüfung dieser Seite fehlgeschlagen; Teilnehmer bleiben erhalten")
                            if result.status == "success":
                                result.status = "partial"
                        result.timings["page_wall_seconds"] += time.perf_counter() - detail_start
                        raw["status"] = result.status
                        write_json(raw_path, raw)
                        last_attempt = max(i for i, attempt in enumerate(history) if attempt.page_id == result.page_id)
                        history[last_attempt] = result
                        write_jsonl(history_path, [row.model_dump() for row in history])
                        write_jsonl(checkpoint_path, [row.model_dump() for row in page_results])
                    if signature_model:
                        resource["signature_model"] = signature_model.resources()
                        resource["warmup_calls"] = resource.get("warmup_calls", 0) + resource["signature_model"].get("warmup_calls", 0)
                        peak = resource["signature_model"].get("peak_gpu_allocated_bytes")
                        if peak is not None:
                            resource["peak_gpu_allocated_bytes"] = max(resource.get("peak_gpu_allocated_bytes") or 0, peak)
                except Exception as exc:
                    resource.setdefault("signature_load_attempt_wall_seconds", time.perf_counter() - signature_load_start)
                    for result in pending:
                        result.review_notes.append(f"Signaturprüfung nicht verfügbar: {type(exc).__name__}")
                        if result.status == "success":
                            result.status = "partial"
                    progress.log(f"{method}: Signaturprüfung nicht abgeschlossen ({type(exc).__name__}); Teilnehmer bleiben erhalten")
                finally:
                    if signature_model:
                        signature_model.close()
                    for result in pending:
                        matches = [i for i, attempt in enumerate(history) if attempt.page_id == result.page_id]
                        if matches:
                            history[matches[-1]] = result
                    write_jsonl(history_path, [row.model_dump() for row in history])
                    write_jsonl(checkpoint_path, [row.model_dump() for row in page_results])
                    gc.collect()
        for key in ("load_seconds", "warmup_seconds", "warmup_calls", "load_attempt_wall_seconds",
                    "signature_load_attempt_wall_seconds", "http_model_requests", "oauth_token_requests"):
            resource[key] = resource.get(key, 0) + prior_resource.get(key, 0)
        for key in ("peak_gpu_allocated_bytes", "peak_gpu_reserved_bytes"):
            values = [v for v in (resource.get(key), prior_resource.get(key)) if v is not None]
            resource[key] = max(values) if values else None
        resource = {**prior_resource, **resource}
        resource["calls"] = sum(r.calls for r in history)
        if resource.get("load_failed"):
            resource["load_seconds"] = max(resource["load_seconds"], resource["load_attempt_wall_seconds"])
        for page in page_results:
            raw_path = method_dir / f"raw-{page.page_id}.json"
            if raw_path.exists():
                raw_records.append(read_json(raw_path))
        write_jsonl(method_dir / "raw.jsonl", raw_records)
        write_jsonl(method_dir / "extractions.jsonl", [r.model_dump() for r in page_results])
        timing_rows = [dict(page_id=r.page_id, status=r.status, **r.timings) for r in page_results]
        write_csv(method_dir / "timings.csv", timing_rows)
        document_times = {}
        for page in page_results:
            entry = document_times.setdefault(page.document_id, dict(document_id=page.document_id, pages=0,
                                             page_processing_seconds=0.0))
            entry["pages"] += 1
            entry["page_processing_seconds"] += page.timings.get("page_wall_seconds", 0.0)
        write_csv(method_dir / "document_timings.csv", list(document_times.values()))
        write_json(
            method_dir / "resources.json",
            dict(
                resource,
                peak_ram_rss_bytes=memory.peak,
                ram_scope="sampled 100ms process + children RSS, shared pages may be counted twice",
            ),
        )
        extraction_charge = sum(
            sum(
                v
                for k, v in r.timings.items()
                if k
                in (
                    "structure_seconds",
                    "signature_seconds",
                    "model_extraction_seconds",
                    "assignment_seconds",
                    "page_overhead_seconds",
                )
            )
            for r in history
        )
        seen_ocr_pages = set()
        for attempt in history:
            if attempt.page_id not in seen_ocr_pages:
                extraction_charge += attempt.timings.get("ocr_charged_seconds", 0.0)
                seen_ocr_pages.add(attempt.page_id)
            else:
                extraction_charge += attempt.timings.get("ocr_lookup_wall_seconds", 0.0)
        preparation_charge = (
            manifest["preparation_seconds"] if scope == "end-to-end" else 0.0
        ) + image_preparation_seconds
        full_charge = (preparation_charge + extraction_charge + resource.get("load_attempt_wall_seconds", 0.0)
                       + resource.get("signature_load_attempt_wall_seconds", 0.0))
        valid_pages = sum(r.parse_status == "valid" or
                          r.output_kind == "ocr_text" and r.status == "success" for r in page_results)
        output_participants = [p for r in page_results for p in r.participants]
        unknown_fields = sum(
            getattr(p, field).state not in ("read", "empty")
            for p in output_participants
            for field in ("first_name", "last_name", "personnel_number", "department")
        )
        summaries[method] = {
            "output_kind": ("ocr_text" if method == "unlimited_ocr" and
                            config.models[method].options.get("extraction", "none") == "none" else "structured"),
            "status": aggregate_status(page_results),
            "selected_pages": len(page_results),
            "text_fallback_pages": sum(r.text_fallback for r in page_results),
            "valid_pages": valid_pages,
            "schema_failure_pages": sum(r.parse_status == "invalid" for r in page_results),
            "failed_pages": sum(r.status == "failed" for r in page_results),
            "unavailable_pages": sum(r.status == "unavailable" for r in page_results),
            "actual_method_wall_seconds": time.perf_counter() - method_start,
            "preprocessing_charged_seconds": preparation_charge,
            "extraction_charged_seconds": extraction_charge,
            "load_seconds": resource.get("load_seconds", 0.0),
            "warmup_seconds": resource.get("warmup_seconds", 0.0),
            "full_pipeline_charged_seconds": full_charge,
            "valid_pages_per_second": valid_pages / full_charge if full_charge and valid_pages else None,
            "peak_ram_rss_bytes": memory.peak,
            "peak_gpu_allocated_bytes": resource.get("peak_gpu_allocated_bytes"),
            "load_attempt_wall_seconds": resource["load_attempt_wall_seconds"],
            "output_text_fields": 4 * len(output_participants),
            "output_unknown_text_fields": unknown_fields,
            "output_signature_fields": len(output_participants),
            "signature_backend": config.signature.backend,
            "model_backend": config.models[method].backend if method in config.models else "ocr_rules",
            "assignment_backend": ("local_llm" if method == "unlimited_ocr" and
                                   config.models[method].options.get("extraction") == "llm" else None),
            "signature_model_load_seconds": resource.get("signature_load_attempt_wall_seconds", 0.0),
            "output_unknown_signatures": sum(p.signature_present is None for p in output_participants),
            "generation_calls": sum(r.calls for r in history),
            "warmup_calls": resource.get("warmup_calls", 0),
            "retries": len(history) - len({r.page_id for r in history}),
            "resume_reused_pages": sum(r.page_id in cached for r in page_results),
        }
        results[method] = page_results
        progress.log(f"{method} abgeschlossen: {summaries[method]['status']}; "
                     f"{valid_pages}/{len(page_results)} Seiten mit gültiger Ausgabe, "
                     f"{len(output_participants)} Einträge; {summaries[method]['actual_method_wall_seconds']:.1f}s")
        if truths is not None and summaries[method]["output_kind"] == "structured":
            with progress.activity(f"{method}: Ergebnisse mit der Ground Truth vergleichen"):
                metrics[method], details = evaluate_groups(page_results, truths)
            write_csv(method_dir / "evaluation_details.csv", details)
    write_json(output / "summary.json", summaries)
    write_jsonl(output / "errors.jsonl", errors)
    write_csv(
        output / "review_pages.csv",
        [
            dict(page_id=p["page_id"], page_number=p["page_number"], reasons=" | ".join(p["reasons"]))
            for p in manifest["pages"]
            if p["review_required"]
        ],
    )
    with progress.activity("HTML-Bericht und CSV-Ergebnisse erstellen"):
        report(output, summaries, results, metrics, manifest, cost_scenario(config))
    write_json(
        output / "run_timing.json",
        {
            "actual_run_wall_seconds": time.perf_counter() - started,
            "scope": scope,
            "resume": bool(resume),
            "quality_measured": truths is not None,
            "truth_pages_in_scope": len(truths) if truths is not None else None,
        },
    )
    print(f"Report: {(output / 'report.html').resolve()}", flush=True)
    progress.log(f"Lauf beendet nach {time.perf_counter() - started:.1f}s; Bericht: {(output / 'report.html').resolve()}")
    progress.log(f"Statusprotokoll: {(output / 'progress.log').resolve()}")
    return output, summaries
