"""PDFs sammeln, Originale sichern und optional PDF-Anmerkungen entfernen."""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOFTWARE_ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["source", "destination", "number", "sha256", "status", "reason",
          "original_destination", "original_status", "comparison_destination", "comparison_status",
          "output_sha256", "annotations_removed", "redactions_preserved"]
PROBLEM_STATUSES = {"conflict", "error"}


def document_number(filename: str) -> str:
    """Sechsstellige ID hinter der Stammnummer und optionalem zweistelligem Präfix."""
    stem = Path(filename).stem
    if re.fullmatch(r"[0-9]{6}", stem):
        return stem
    match = re.match(
        r"^(?:[0-9]{2}\.\s*)?[0-9]+\s*[._-]\s*([0-9]+)(?=[_.\s-]|$)",
        stem,
    )
    if not match:
        raise ValueError("Keine gültige ID nach der Stammnummer erkannt")
    if len(match.group(1)) != 6:
        raise ValueError("Die ID muss genau 6 Ziffern enthalten")
    return match.group(1)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def inventory(root: Path):
    def on_error(error):
        raise error

    for directory, folders, files in os.walk(root, followlinks=False, onerror=on_error):
        folders.sort()
        for name in folders[:]:
            path = Path(directory) / name
            if is_link(path):
                folders.remove(name)
                yield path, True
        for name in sorted(files):
            path = Path(directory) / name
            yield path, is_link(path)


def copy_exclusive(source: Path, destination: Path, expected_hash: str):
    """Vorhandene Ziele niemals überschreiben; unvollständige Kopien entfernen."""
    with source.open("rb") as incoming:
        outgoing = destination.open("xb")
        try:
            with outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
            if file_hash(destination) != expected_hash:
                raise OSError("Quelldatei wurde beim Kopieren verändert oder Kopie ist unvollständig")
        except BaseException:
            destination.unlink(missing_ok=True)
            raise


def validate_destination(root: Path, destination: Path) -> None:
    if is_link(root) or is_link(destination) or not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Ziel verweist außerhalb des Ausgabeordners oder ist eine Verknüpfung")


def comparison_paths(output_root: Path, source: Path, relative_source: str,
                     number: str, digest: str) -> tuple[Path, Path, Path]:
    # Include provenance as well as content: identical PDFs in different input
    # folders still receive individual pairs with their original filenames.
    key = hashlib.sha256((relative_source + "\0" + digest).encode("utf-8")).hexdigest()[:12]
    root = output_root / "vergleich"
    folder = root / f"{number or 'ohne_id'}_{key}"
    edited_name = f"{number or 'dokument'}_bearbeitet.pdf"
    if edited_name.casefold() == source.name.casefold():
        edited_name = f"{number or 'dokument'}_bearbeitet_1.pdf"
    validate_destination(root, folder)
    original, edited = folder / source.name, folder / edited_name
    validate_destination(folder, original)
    validate_destination(folder, edited)
    return folder, original, edited


def preprocess(input_root: Path, output_root: Path, *, dry_run: bool = False,
               remove_annotations: bool = False) -> dict:
    # Keep the original copy-only Python API available; CLI cleanup is enabled by default.
    if remove_annotations:
        try:
            if __package__:
                from .markierungen import cleaned_pdf, write_exclusive
            else:
                from markierungen import cleaned_pdf, write_exclusive
        except ImportError as exc:
            raise RuntimeError("PyMuPDF fehlt; aus software/ mit uv sync --locked --extra models installieren") from exc
    input_root, output_root = input_root.resolve(), output_root.resolve()
    if not input_root.is_dir():
        raise ValueError(f"Eingabeordner existiert nicht: {input_root}")
    if input_root.is_relative_to(output_root) or output_root.is_relative_to(input_root):
        raise ValueError("Eingabe- und Ausgabeordner dürfen sich nicht überlappen")
    entries, planned, original_plans = [], {}, set()
    for source, linked in inventory(input_root):
        entry = dict.fromkeys(FIELDS, "")
        entry["source"] = str(source.relative_to(input_root))
        entries.append(entry)
        if linked:
            entry.update(status="skipped_link", reason="Verknüpfung wird nicht verfolgt")
            continue
        if source.suffix.lower() != ".pdf":
            entry.update(status="skipped_non_pdf", reason="Kein PDF-Dateityp")
            continue
        rejection_reason = ""
        try:
            number = document_number(source.name)
            target_root = output_root / "pdfs"
            target_name = f"{number}.pdf"
        except ValueError as exc:
            rejection_reason = str(exc)
            number = ""
            target_root = output_root / "nicht_erfuellt"
            target_name = source.name
        destination = target_root / target_name
        entry.update(number=number, destination=str(destination.relative_to(output_root)))
        try:
            validate_destination(target_root, destination)
            digest = file_hash(source)
            entry["sha256"] = digest
            cleaned_data = None
            output_digest = digest
            if remove_annotations:
                # Archive each source before editing; retain its exact original name.
                comparison_root, original, edited = comparison_paths(
                    output_root, source, entry["source"], number, digest,
                )
                entry.update(original_destination=str(original.relative_to(output_root)),
                             comparison_destination=str(edited.relative_to(output_root)))
                if original.exists():
                    if not original.is_file() or file_hash(original) != digest:
                        raise ValueError("Vorhandene Originalsicherung weicht von der Quelle ab")
                    entry["original_status"] = "already_present"
                elif dry_run:
                    entry["original_status"] = "duplicate" if original in original_plans else "would_copy"
                else:
                    comparison_root.mkdir(parents=True, exist_ok=True)
                    copy_exclusive(source, original, digest)
                    entry["original_status"] = "copied"
                original_plans.add(original)
                cleaned_data, removed, preserved = cleaned_pdf(source)
                entry.update(annotations_removed=removed, redactions_preserved=preserved)
                if file_hash(source) != digest:
                    raise ValueError("Quelldatei wurde während der Bereinigung verändert")
                if cleaned_data is not None:
                    output_digest = hashlib.sha256(cleaned_data).hexdigest()
                entry["output_sha256"] = output_digest
                # Complete the individual pair even if the shared ID destination
                # below conflicts with another source bearing the same course ID.
                if edited.exists():
                    if not edited.is_file() or file_hash(edited) != output_digest:
                        raise ValueError("Vorhandene bearbeitete Vergleichskopie weicht ab")
                    entry["comparison_status"] = "already_present"
                elif dry_run:
                    entry["comparison_status"] = "would_copy"
                else:
                    if cleaned_data is None:
                        copy_exclusive(source, edited, digest)
                    else:
                        write_exclusive(edited, cleaned_data)
                    entry["comparison_status"] = "copied"
            key = str(destination).casefold()
            previous = planned.get(key)
            if previous is not None:
                same = previous == digest
                entry.update(
                    status="duplicate" if same else "conflict",
                    reason="Gleicher Zielname und gleicher Inhalt" if same else "Gleicher Zielname, anderer Inhalt",
                )
            elif destination.exists():
                existing_digest = file_hash(destination) if destination.is_file() else None
                if existing_digest == output_digest:
                    entry.update(status="already_present", reason="Identische Datei vorhanden")
                    planned[key] = digest
                elif cleaned_data is not None and existing_digest == digest:
                    # Upgrade an earlier byte-identical working copy only after archiving its original.
                    if dry_run:
                        entry.update(status="would_update", reason="Würde vorhandene Originalkopie bereinigen")
                    else:
                        temporary = destination.parent / f".cleanup-{uuid.uuid4().hex}.tmp"
                        try:
                            write_exclusive(temporary, cleaned_data)
                            if file_hash(destination) != digest:
                                raise ValueError("Zieldatei wurde während der Bereinigung verändert")
                            temporary.replace(destination)
                        finally:
                            temporary.unlink(missing_ok=True)
                        entry.update(status="updated", reason="Vorhandene Originalkopie bereinigt; Original gesichert")
                    planned[key] = digest
                else:
                    entry.update(status="conflict", reason="Abweichendes Ziel bereits vorhanden")
            elif dry_run:
                planned[key] = digest
                entry.update(
                    status="would_copy_rejected" if rejection_reason else "would_copy",
                    reason="Würde aussortiert" if rejection_reason else "Würde kopiert und umbenannt",
                )
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if cleaned_data is None:
                    copy_exclusive(source, destination, digest)
                else:
                    write_exclusive(destination, cleaned_data)
                planned[key] = digest
                entry.update(
                    status="copied_rejected" if rejection_reason else "copied",
                    reason="Aussortiert" if rejection_reason else "Kopiert und umbenannt",
                )
        except (OSError, ValueError, RuntimeError) as exc:
            entry.update(status="error", reason=str(exc))
        if rejection_reason:
            entry["reason"] += f"; {rejection_reason}"
    report = {
        "version": 3,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_root": str(input_root),
        "output_root": str(output_root),
        "dry_run": dry_run,
        "remove_annotations": remove_annotations,
        "summary": dict(Counter(entry["status"] for entry in entries)),
        "entries": entries,
    }
    if not dry_run:
        reports = output_root / "protokolle"
        if is_link(reports):
            raise ValueError("Protokollordner darf keine Verknüpfung sein")
        reports.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        report_path = reports / f"{stamp}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        with report_path.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(entries)
        report["report_path"] = str(report_path)
    return report


def print_summary(report: dict):
    counts = report["summary"]
    links = counts.get("skipped_link", 0)
    other_files = counts.get("skipped_non_pdf", 0)
    files = len(report["entries"]) - links
    pdfs = files - other_files
    valid_ids = sum(bool(entry["number"]) for entry in report["entries"])
    dry_run = report["dry_run"]
    copied = counts.get("would_copy" if dry_run else "copied", 0)
    rejected = counts.get("would_copy_rejected" if dry_run else "copied_rejected", 0)
    print("\nZusammenfassung" + (" (Probelauf):" if dry_run else ":"))
    rows = [
        ("Dateien gefunden", files),
        ("Davon PDFs", pdfs),
        ("Andere Dateien übersprungen", other_files),
        ("ID gültig / nicht erfüllt", f"{valid_ids} / {pdfs - valid_ids}"),
        ("Würden kopiert" if dry_run else "Neu kopiert", copied + rejected),
        ("Davon nach nicht_erfuellt", rejected),
        ("Bereits identisch vorhanden", counts.get("already_present", 0)),
        ("Duplikate übersprungen", counts.get("duplicate", 0)),
        ("Namenskonflikte", counts.get("conflict", 0)),
        ("Fehler", counts.get("error", 0)),
    ]
    if links:
        rows.append(("Verknüpfungen übersprungen", links))
    if report.get("remove_annotations"):
        changed = {"would_copy", "would_copy_rejected", "would_update"} if dry_run else {"copied", "copied_rejected", "updated"}
        removed = sum(int(entry["annotations_removed"] or 0) for entry in report["entries"]
                      if entry["status"] in changed or entry["comparison_status"] == ("would_copy" if dry_run else "copied"))
        backups = sum(entry["original_status"] == ("would_copy" if dry_run else "copied") for entry in report["entries"])
        rows.extend([
            ("Originale würden gesichert" if dry_run else "Originale neu gesichert", backups),
            ("Vergleichskopien geplant" if dry_run else "Vergleichskopien neu erstellt",
             sum(entry["comparison_status"] == ("would_copy" if dry_run else "copied") for entry in report["entries"])),
            ("Vorhandene würden bereinigt" if dry_run else "Vorhandene Kopien bereinigt",
             counts.get("would_update" if dry_run else "updated", 0)),
            ("Anmerkungen würden entfernt" if dry_run else "Anmerkungen entfernt", removed),
        ])
    for label, value in rows:
        print(f"  {label + ':':<30} {value}")
    if pdfs == 0:
        result = "Keine PDFs gefunden"
    elif PROBLEM_STATUSES.intersection(counts):
        result = "Mit Konflikten oder Fehlern beendet; Details siehe oben"
    else:
        result = "Probelauf erfolgreich" if dry_run else "Erfolgreich abgeschlossen"
    print(f"  Ergebnis: {result}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PDFs rekursiv sammeln und nach Dokumentnummer umbenennen")
    parser.add_argument("--input", type=Path, default=SOFTWARE_ROOT.parent / "dateien")
    parser.add_argument("--output", type=Path, default=SOFTWARE_ROOT / "vorverarbeitung" / "ausgabe")
    parser.add_argument("--dry-run", action="store_true", help="Nur prüfen, keine Dateien oder Ordner anlegen")
    parser.add_argument("--keep-annotations", action="store_true", help="Nur wie bisher kopieren; keine Anmerkungsbereinigung")
    args = parser.parse_args(argv)
    try:
        report = preprocess(args.input, args.output, dry_run=args.dry_run, remove_annotations=not args.keep_annotations)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    for entry in report["entries"]:
        if entry["status"] != "skipped_non_pdf":
            print(f"{entry['status']}: {entry['source']} -> {entry['destination']} ({entry['reason']})")
    if "report_path" in report:
        print(f"Protokoll: {report['report_path']}")
    print_summary(report)
    if not any(entry["destination"] for entry in report["entries"]):
        return 1
    return 1 if PROBLEM_STATUSES.intersection(report["summary"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
