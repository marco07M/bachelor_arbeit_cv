"""Render original PDFs once; curate inclusion and extra clockwise rotation in a manifest."""

import time
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

from .io import digest, file_hash, read_json, write_json


def inventory(folder: Path, recursive: bool):
    if not folder.is_dir():
        raise ValueError(f"Input folder does not exist: {folder}")
    files = sorted(folder.rglob("*") if recursive else folder.iterdir())
    return [
        {
            "path": str(p.resolve()),
            "sha256": file_hash(p),
            "kind": "pdf" if p.suffix.lower() == ".pdf" else "skipped_non_pdf",
        }
        for p in files
        if p.is_file()
    ]


def classify(image, ocr):
    pixels = np.asarray(image.convert("L"))
    ink_fraction = float(np.mean(pixels < 180))
    if ink_fraction < 0.0001:
        return "blank", False, False, ["Nearly white rendered page; no relevant visible content"]
    text = ocr.get("text", "").casefold()
    groups = [
        ("vorname", "first name"),
        ("nachname", "familienname", "last name"),
        ("personalnummer", "personalnr", "persnr"),
        ("abteilung", "department"),
        ("unterschrift", "signature"),
    ]
    hits = sum(any(word in text for word in group) for group in groups)
    if hits >= 3:
        return "participant_list", True, False, [f"{hits} independent participant-field headers detected"]
    return "uncertain", True, True, [f"Only {hits} header groups; conservatively retained for review"]


def prepare(folder: Path, config, output: Path, ocr=None):
    start = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    images = output / "pages"
    images.mkdir()
    inputs = inventory(folder, config.pdf.recursive)
    pages, errors, seen = [], [], set()
    for item in inputs:
        if item["kind"] != "pdf":
            errors.append({"path": item["path"], "status": "skipped", "reason": item["kind"]})
            continue
        document_id = item["sha256"]
        if document_id in seen:
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
                for number, page in enumerate(doc, 1):
                    page_start = time.perf_counter()
                    page_id = f"{document_id}-p{number:04d}"
                    record = {
                        "document_id": document_id,
                        "page_number": number,
                        "page_id": page_id,
                        "source_path": item["path"],
                        "source_sha256": document_id,
                        "pdf_rotation_metadata": page.rotation,
                        "embedded_text_layer": bool(page.get_text().strip()),
                        "additional_rotation_clockwise": 0,
                        "curation_rotation_clockwise": 0,
                        "curation_note": None,
                        "split": None,
                        "dependency_group": document_id,
                    }
                    try:
                        # get_pixmap already applies PDF rotation metadata. Never apply it twice.
                        pixmap = page.get_pixmap(dpi=config.pdf.dpi, alpha=False, colorspace=pymupdf.csRGB)
                        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                        orientation_notes, orientation_s = [], 0.0
                        if config.pdf.auto_orient and ocr:
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
                        lookup_start = time.perf_counter()
                        try:
                            ocr_data = ocr.recognize(image, image_hash) if ocr else {}
                        except Exception as exc:
                            ocr_data = {}
                            orientation_notes.append(f"Classification OCR failed; page retained: {exc}")
                        lookup_seconds = time.perf_counter() - lookup_start
                        page_type, included, review, reasons = classify(image, ocr_data)
                        record.update(
                            image=str(image_path.relative_to(output)),
                            image_sha256=image_hash,
                            width=image.width,
                            height=image.height,
                            page_type=page_type,
                            include=included,
                            review_required=review or bool(orientation_notes),
                            reasons=reasons + orientation_notes,
                            status="ready",
                            orientation_seconds=orientation_s,
                            classification_ocr_seconds=ocr_data.get("elapsed_seconds", 0.0),
                            classification_ocr_wall_seconds=lookup_seconds,
                            preparation_seconds=time.perf_counter() - page_start,
                        )
                        image.close()
                    except Exception as exc:
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
            errors.append(
                {"path": item["path"], "document_id": document_id, "status": "failed", "reason": str(exc)}
            )
    manifest = {
        "version": 1,
        "input_root": str(folder.resolve()),
        "inputs": inputs,
        "preprocessing_config": config.model_dump(),
        "pages": pages,
        "errors": errors,
        "preparation_seconds": time.perf_counter() - start,
        "curated": False,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def validate_manifest(path: Path, folder: Path, config):
    manifest = read_json(path)
    if manifest.get("version") != 1:
        raise ValueError("Unsupported manifest version")
    if manifest["preprocessing_config"]["pdf"] != config.pdf.model_dump():
        raise ValueError("PDF preprocessing configuration changed; prepare a new manifest")
    current = inventory(folder, config.pdf.recursive)
    if current != manifest["inputs"]:
        raise ValueError("Input paths/hashes changed; prepare a new manifest")
    seen = set()
    splits = {}
    for page in manifest["pages"]:
        identity = (page["document_id"], page["page_number"])
        if identity in seen or page["page_id"] != f"{identity[0]}-p{identity[1]:04d}":
            raise ValueError("Duplicate or inconsistent page identity")
        seen.add(identity)
        if page.get("split") not in (None, "development", "test"):
            raise ValueError("Manifest split must be development/test/null")
        if page.get("split") is not None:
            splits.setdefault(page.get("dependency_group", page["document_id"]), set()).add(page["split"])
            splits.setdefault(page["document_id"], set()).add(page["split"])
        if type(page["include"]) is not bool:
            raise ValueError("include must be a JSON boolean")
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
