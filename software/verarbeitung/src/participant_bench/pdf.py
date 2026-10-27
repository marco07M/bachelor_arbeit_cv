"""Render every input PDF page; optional orientation and explicit manual curation only."""

import time
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps

from .io import digest, file_hash, read_json, write_json
from .progress import Progress


def inventory(folder: Path, recursive: bool, progress: Progress | None = None, include_images=False):
    if not folder.is_dir():
        raise ValueError(f"Input folder does not exist: {folder}")
    progress = progress or Progress(enabled=False)
    files = [p for p in sorted(folder.rglob("*") if recursive else folder.iterdir()) if p.is_file()]
    entries = []
    with progress.activity(f"Eingabedateien erfassen und Prüfsummen bilden ({len(files)} Dateien)"):
        for index, path in enumerate(files, 1):
            progress.log(f"Eingabe [{index}/{len(files)}]: {path.name}")
            entries.append({
                "path": str(path.resolve()), "sha256": file_hash(path),
                "kind": ("pdf" if path.suffix.lower() == ".pdf" else "image" if include_images and
                         path.suffix.lower() in (".png", ".jpg", ".jpeg") else "skipped_non_pdf"),
            })
    return entries


def prepare(folder: Path, config, output: Path, ocr=None, progress: Progress | None = None):
    start = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    images = output / "pages"
    images.mkdir()
    progress = progress or Progress(enabled=False)
    progress.log("PDF-Vorbereitung starten")
    inputs = inventory(folder, config.pdf.recursive, progress, include_images=config.pdf.include_images)
    pdf_count = sum(item["kind"] in ("pdf", "image") for item in inputs)
    pdf_index = 0
    pages, errors, seen = [], [], set()
    for item in inputs:
        if item["kind"] not in ("pdf", "image"):
            progress.log(f"Übersprungen: {Path(item['path']).name} ist kein PDF")
            errors.append({"path": item["path"], "status": "skipped", "reason": item["kind"]})
            continue
        pdf_index += 1
        name = Path(item["path"]).name
        progress.log(f"PDF [{pdf_index}/{pdf_count}]: {name} öffnen")
        document_id = item["sha256"]
        if document_id in seen:
            progress.log(f"PDF {name}: identisches Duplikat, wird übersprungen")
            errors.append(
                {
                    "path": item["path"],
                    "status": "duplicate",
                    "reason": "Identical PDF hash",
                    "document_id": document_id,
                }
            )
            continue
        seen.add(document_id)
        try:
            with pymupdf.open(item["path"]) as doc:
                if doc.needs_pass:
                    raise ValueError("Encrypted PDF requires password; not processed")
                progress.log(f"PDF {name}: {doc.page_count} Seiten gefunden")
                for number, page in enumerate(doc, 1):
                    label = f"{name}, Seite {number}/{doc.page_count}"
                    progress.log(f"Vorbereitung: {label}; " +
                                 ("Bildpixel übernehmen" if item["kind"] == "image" else f"rendern mit {config.pdf.dpi} DPI"))
                    page_start = time.perf_counter()
                    page_id = f"{document_id}-p{number:04d}"
                    record = {
                        "document_id": document_id,
                        "page_number": number,
                        "page_id": page_id,
                        "source_path": item["path"],
                        "source_sha256": document_id,
                        "source_kind": item["kind"],
                        "pdf_rotation_metadata": page.rotation,
                        "embedded_text_layer": bool(page.get_text().strip()),
                        "additional_rotation_clockwise": 0,
                        "curation_rotation_clockwise": 0,
                        "curation_note": None,
                        "split": None,
                        "dependency_group": document_id,
                    }
                    if config.ocr.source == "prefer_pdf":
                        embedded = []
                        for word in page.get_text("words", sort=True):
                            box = pymupdf.Rect(word[:4]) * page.rotation_matrix
                            if box.width > 0 and box.height > 0:
                                embedded.append({"text": word[4], "line": [int(word[5]) + 1, 1, int(word[6]) + 1],
                                    "bbox": dict(x0=max(0, box.x0 / page.rect.width), y0=max(0, box.y0 / page.rect.height),
                                                 x1=min(1, box.x1 / page.rect.width), y1=min(1, box.y1 / page.rect.height))})
                        # A digital heading over a scanned table is not a usable full-page text source.
                        substantial_raster = any(pymupdf.Rect(info["bbox"]).get_area() > page.rect.get_area() * 0.1
                                                 for info in page.get_image_info())
                        record["embedded_words"] = [] if substantial_raster else embedded
                        record["embedded_text_rejection"] = "substantial_raster_content" if substantial_raster else None
                    try:
                        # get_pixmap already applies PDF rotation metadata. Never apply it twice.
                        if item["kind"] == "image":
                            with Image.open(item["path"]) as source_image:
                                record["image_exif_orientation"] = source_image.getexif().get(274, 1)
                                image = ImageOps.exif_transpose(source_image).convert("RGB")
                        else:
                            pixmap = page.get_pixmap(dpi=config.pdf.dpi, alpha=False, colorspace=pymupdf.csRGB)
                            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                        orientation_notes, orientation_s = [], 0.0
                        if config.pdf.auto_orient and ocr:
                            with progress.activity(f"Ausrichtung prüfen: {label}"):
                                rotation, confidence, error, orientation_s = ocr.orientation(image)
                            record["orientation_confidence"] = confidence
                            if confidence >= config.pdf.osd_min_confidence:
                                image = image.rotate(-rotation, expand=True)
                                record["additional_rotation_clockwise"] = rotation
                            else:
                                orientation_notes.append(
                                    "Orientation uncertain; visually review 0/90/180/270"
                                )
                            if error:
                                record["orientation_error"] = error
                        elif config.pdf.auto_orient:
                            orientation_notes.append("OSD unavailable; orientation needs review")
                        image_path = images / f"{page_id}.png"
                        image.save(image_path)
                        image_hash = file_hash(image_path)
                        record.update(
                            image=str(image_path.relative_to(output)),
                            image_sha256=image_hash,
                            width=image.width,
                            height=image.height,
                            page_type="input_page",
                            include=True,
                            review_required=bool(orientation_notes),
                            reasons=["Input page supplied for extraction; no automatic page classification"] + orientation_notes,
                            status="ready",
                            orientation_seconds=orientation_s,
                            preparation_seconds=time.perf_counter() - page_start,
                        )
                        image.close()
                        progress.log(
                            f"Vorbereitet: {label}; bereit für Teilnehmerextraktion, "
                            f"zusätzliche Drehung={record['additional_rotation_clockwise']}°, "
                            f"{time.perf_counter() - page_start:.1f}s"
                        )
                    except Exception as exc:
                        progress.log(f"Seitenfehler: {label}: {type(exc).__name__}: {exc}")
                        record.update(
                            status="failed",
                            include=True,
                            review_required=True,
                            reasons=[str(exc)],
                            page_type="unreadable",
                        )
                        errors.append({"page_id": page_id, "status": "failed", "reason": str(exc)})
                    pages.append(record)
        except Exception as exc:
            progress.log(f"PDF-Fehler: {name}: {type(exc).__name__}: {exc}")
            errors.append(
                {"path": item["path"], "document_id": document_id, "status": "failed", "reason": str(exc)}
            )
    manifest = {
        "version": 2,
        "automatic_page_selection": False,
        "input_root": str(folder.resolve()),
        "inputs": inputs,
        "preprocessing_config": config.model_dump(),
        "pages": pages,
        "errors": errors,
        "preparation_seconds": time.perf_counter() - start,
        "curated": False,
    }
    write_json(output / "manifest.json", manifest)
    progress.log(f"PDF-Vorbereitung fertig: {len(pages)} Seiten, "
                 f"alle für die Extraktion enthalten; {len(errors)} protokollierte Hinweise/Fehler")
    return manifest


def validate_manifest(path: Path, folder: Path, config, progress: Progress | None = None):
    manifest = read_json(path)
    if manifest.get("version") != 2 or manifest.get("automatic_page_selection") is not False:
        raise ValueError("Altes Seitenmanifest mit automatischer Seitenauswahl; mit prepare neu erzeugen")
    if manifest["preprocessing_config"]["pdf"] != config.pdf.model_dump():
        raise ValueError("PDF preprocessing configuration changed; prepare a new manifest")
    current = inventory(folder, config.pdf.recursive, progress, include_images=config.pdf.include_images)
    if current != manifest["inputs"]:
        raise ValueError("Input paths/hashes changed; prepare a new manifest")
    seen = set()
    splits = {}
    for page in manifest["pages"]:
        identity = (page["document_id"], page["page_number"])
        if identity in seen or page["page_id"] != f"{identity[0]}-p{identity[1]:04d}":
            raise ValueError("Duplicate or inconsistent page identity")
        seen.add(identity)
        if page.get("split") not in (None, "development", "validation", "test"):
            raise ValueError("Manifest split must be development/validation/test/null")
        if page.get("split") is not None:
            splits.setdefault(page.get("dependency_group", page["document_id"]), set()).add(page["split"])
            splits.setdefault(page["document_id"], set()).add(page["split"])
        if type(page["include"]) is not bool:
            raise ValueError("include must be a JSON boolean")
        if not page["include"] and not manifest.get("curated"):
            raise ValueError("Seiten nur in einem manuell geprüften Manifest mit curated=true ausschließen")
        rotation = page.get("curation_rotation_clockwise", 0)
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Curation rotation must be 0/90/180/270")
        if page["status"] == "ready":
            image = path.parent / page["image"]
            if file_hash(image) != page["image_sha256"]:
                raise ValueError(f"Rendered image changed: {page['page_id']}")
    if any(len(group) > 1 for group in splits.values()):
        raise ValueError("Manifest document/dependency group crosses development/test boundary")
    return manifest


def run_identity(config, manifest, model_identities):
    return digest(
        {
            "config": config.model_dump(),
            "manifest": manifest,
            "models": model_identities,
            "implementation": "participant-bench-v1",
        }
    )
