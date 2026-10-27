"""Manual CSV references, immutable source hashes and grouped development/validation/test splits."""

import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from ..io import digest, file_hash, read_json, write_csv, write_json
from ..schema import TEXT_FIELDS, Box, GroundTruthPage, Participant, TextField

SPLITS = ("development", "validation", "test")


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def yes(value: str) -> bool:
    return value.strip().casefold() in ("true", "1", "yes", "ja")


def initialize(folder: Path, output: Path, sample_documents: int | None = None, seed=42) -> Path:
    if output.exists():
        raise ValueError("Referenzordner existiert bereits; keine Referenzen überschreiben")
    inventory, errors = {}, []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        document_id = file_hash(path)
        if document_id in inventory:
            inventory[document_id]["duplicates"].append(str(path.relative_to(folder)))
            continue
        try:
            with pymupdf.open(path) as document:
                if document.needs_pass:
                    raise ValueError("encrypted")
                count = document.page_count
            inventory[document_id] = dict(
                document_id=document_id, path=str(path.relative_to(folder)), pages=count, duplicates=[]
            )
        except Exception as exc:
            errors.append({"document_id": document_id, "error_type": type(exc).__name__})
    if not inventory:
        raise ValueError("Keine lesbaren PDFs für Referenzdatensatz")
    if sample_documents is not None:
        if sample_documents < 5:
            raise ValueError("Stichprobe benötigt mindestens fünf Dokumente")
        selected = random.Random(seed).sample(sorted(inventory), min(sample_documents, len(inventory)))
        inventory = {key: inventory[key] for key in sorted(selected)}
    output.mkdir(parents=True)
    write_json(
        output / "dataset.json",
        {
            "version": 1,
            "input_root": str(folder.resolve()),
            "documents": list(inventory.values()),
            "errors": errors,
        },
    )
    write_csv(
        output / "documents.csv",
        [
            dict(document_id=d, dependency_group=d, stratum="unassigned", grouping_reviewed="false")
            for d in inventory
        ],
    )
    pages = []
    for doc in inventory.values():
        for number in range(1, doc["pages"] + 1):
            text_file = f"text/{doc['document_id'][:16]}-p{number:04d}.txt"
            target = output / text_file
            target.parent.mkdir(exist_ok=True)
            target.write_text("", encoding="utf-8")
            pages.append(
                dict(
                    document_id=doc["document_id"],
                    page_number=number,
                    reviewed="false",
                    content_type="typed",
                    text_reviewed="false",
                    reference_text_file=text_file,
                    quality_flags="",
                )
            )
    write_csv(output / "pages.csv", pages)
    columns = ["document_id", "page_number", "row_ref", "bbox"]
    columns += [key for field in TEXT_FIELDS for key in (field, field + "_state")]
    write_csv(output / "participants.csv", [], fields=columns + ["signature_present"])
    return output


def assign_groups(documents: list[dict], seed=42, ratios=(0.6, 0.2, 0.2)) -> dict:
    groups = defaultdict(list)
    for doc in documents:
        groups[doc["dependency_group"]].append(doc)
    if len(groups) < 5:
        raise ValueError("Mindestens fünf unabhängige Dokumentgruppen für 60/20/20 erforderlich")
    strata = defaultdict(list)
    for group, members in groups.items():
        strata[tuple(sorted({m["stratum"] for m in members}))].append(group)
    rng, assignment, overall = random.Random(seed), {}, Counter()
    for stratum in sorted(strata):
        identifiers = sorted(strata[stratum])
        rng.shuffle(identifiers)
        counts = Counter()
        for index, group in enumerate(identifiers):
            choice = max(
                range(3),
                key=lambda i: (
                    ratios[i] * (len(assignment) + 1)
                    - overall[SPLITS[i]]
                    + 0.5 * (ratios[i] * (index + 1) - counts[SPLITS[i]]),
                    -i,
                ),
            )
            split = SPLITS[choice]
            assignment[group] = split
            counts[split] += 1
            overall[split] += 1
    for split in SPLITS:
        if not overall[split]:
            donor = max(SPLITS, key=lambda s: overall[s])
            group = sorted(g for g in assignment if assignment[g] == donor)[-1]
            assignment[group] = split
            overall[donor] -= 1
            overall[split] += 1
    return assignment


def split_dataset(folder: Path, seed=42) -> Path:
    destination = folder / "splits.json"
    if destination.exists():
        raise ValueError("Aufteilung ist bereits eingefroren; neuen versionierten Referenzordner verwenden")
    inventory = read_json(folder / "dataset.json")
    documents = rows(folder / "documents.csv")
    expected = {d["document_id"] for d in inventory["documents"]}
    if len(documents) != len(expected) or {d["document_id"] for d in documents} != expected:
        raise ValueError("Dokumentmetadaten fehlen oder sind doppelt")
    if any(not yes(d["grouping_reviewed"]) or not d["dependency_group"].strip() for d in documents):
        raise ValueError("Verwandte Vorlagen/Duplikate gruppieren und grouping_reviewed=true bestätigen")
    if any(not d["stratum"].strip() or d["stratum"] == "unassigned" for d in documents):
        raise ValueError("Layout-/Qualitätsstratum für jedes Dokument manuell angeben")
    assignment = assign_groups(documents, seed)
    document_splits = {d["document_id"]: assignment[d["dependency_group"]] for d in documents}
    write_json(
        destination,
        dict(
            seed=seed,
            ratios=[0.6, 0.2, 0.2],
            groups=assignment,
            documents=document_splits,
            documents_csv_sha256=file_hash(folder / "documents.csv"),
            dataset_sha256=file_hash(folder / "dataset.json"),
            actual_documents=dict(Counter(document_splits.values())),
        ),
    )
    return destination


def load_dataset(folder: Path) -> dict:
    metadata, splits = read_json(folder / "dataset.json"), read_json(folder / "splits.json")
    if (
        file_hash(folder / "documents.csv") != splits["documents_csv_sha256"]
        or file_hash(folder / "dataset.json") != splits["dataset_sha256"]
    ):
        raise ValueError("Dokumentgruppen oder Inventar nach eingefrorener Aufteilung verändert")
    documents = {d["document_id"]: d for d in rows(folder / "documents.csv")}
    inventory = {d["document_id"]: d for d in metadata["documents"]}
    source_root = Path(metadata["input_root"]).resolve()
    for key, doc in inventory.items():
        source = (source_root / doc["path"]).resolve()
        if not source.is_relative_to(source_root) or file_hash(source) != key:
            raise ValueError("Original-PDF fehlt oder wurde verändert; keine Referenzüberschreibung")
        doc["source"] = source
    annotations = defaultdict(list)
    for index, record in enumerate(rows(folder / "participants.csv"), 2):
        key = (record["document_id"], int(record["page_number"]))
        fields = {}
        for name in TEXT_FIELDS:
            state = record[name + "_state"]
            if state not in ("read", "empty", "illegible", "uncertain"):
                raise ValueError(f"Expliziter Referenz-Feldstatus fehlt, CSV-Zeile {index}")
            if state != "read" and record[name]:
                raise ValueError(f"Referenzwert widerspricht dem Feldstatus, CSV-Zeile {index}")
            fields[name] = TextField(
                value=record[name] if state == "read" else "" if state == "empty" else None, state=state
            )
        box = record.get("bbox", "").strip()
        signature = record.get("signature_present", "").strip().casefold()
        if signature not in ("true", "false", "unknown", ""):
            raise ValueError("Signaturreferenz muss true/false/unknown sein")
        present = None if signature in ("", "unknown") else signature == "true"
        annotations[key].append(
            Participant(
                row_ref=record["row_ref"] or None,
                bbox=Box(**dict(zip(("x0", "y0", "x1", "y1"), map(float, box.split(","))))) if box else None,
                **fields,
                signature_present=present,
                signature_state="uncertain" if present is None else "read" if present else "empty",
            )
        )
    pages, texts, flags, seen, hashes = [], {}, {}, set(), {}
    for record in rows(folder / "pages.csv"):
        key = (record["document_id"], int(record["page_number"]))
        if key in seen or key[0] not in inventory or not 1 <= key[1] <= inventory[key[0]]["pages"]:
            raise ValueError("Unbekannte/doppelte Referenzseite")
        seen.add(key)
        if not yes(record["reviewed"]):
            raise ValueError(
                "Alle Seiten einschließlich Deckblättern manuell prüfen und reviewed=true setzen"
            )
        pages.append(
            GroundTruthPage(
                document_id=key[0],
                page_number=key[1],
                split=splits["documents"][key[0]],
                dependency_group=documents[key[0]]["dependency_group"],
                content_type=record["content_type"],
                relevant=bool(annotations[key]),
                participants=annotations[key],
            )
        )
        flags[key] = [flag for flag in record["quality_flags"].split(";") if flag]
        if set(flags[key]) - {
            "poor_image_quality",
            "skew",
            "handwritten",
            "shadow",
            "low_contrast",
            "cropped",
            "wrapped_text",
            "duplicate_template",
        }:
            raise ValueError("Unbekannte Qualitätskategorie; keine Freitexte mit Personendaten verwenden")
        if yes(record["text_reviewed"]):
            path = (folder / record["reference_text_file"]).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise ValueError("Referenztext muss im Referenzordner liegen")
            texts[key] = path.read_text(encoding="utf-8")
            hashes[str(path.relative_to(folder.resolve()))] = file_hash(path)
    expected_pages = sum(d["pages"] for d in inventory.values())
    if len(seen) != expected_pages or set(annotations) - seen:
        raise ValueError("Referenzseiten fehlen oder Teilnehmer wurden einer unbekannten Seite zugeordnet")
    for name in ("dataset.json", "splits.json", "documents.csv", "pages.csv", "participants.csv"):
        hashes[name] = file_hash(folder / name)
    return dict(
        folder=folder.resolve(),
        pages=pages,
        texts=texts,
        quality_flags=flags,
        inventory=inventory,
        dataset_id=digest(hashes),
        hashes=hashes,
    )


def partitions(dataset: dict) -> dict[str, list[GroundTruthPage]]:
    parts = {name: [p for p in dataset["pages"] if p.split == name] for name in SPLITS}
    groups = sorted({p.dependency_group for p in parts["validation"]}, key=lambda key: digest(key))
    midpoint = len(groups) // 2
    fit_groups = set(groups[:midpoint])
    parts["validation_fit"] = [p for p in parts["validation"] if p.dependency_group in fit_groups]
    parts["validation_audit"] = [p for p in parts["validation"] if p.dependency_group not in fit_groups]
    return parts
