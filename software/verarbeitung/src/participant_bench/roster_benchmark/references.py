"""Stream XLSX/CSV reference columns as strings; preserve identifiers and original source row numbers."""

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

from openpyxl import load_workbook

from ..excel_columns import resolve_columns
from ..excel_reference import ReferencePerson, cell_text
from ..io import file_hash, read_json
from .config import ReferenceConfig


@dataclass
class ReferenceData:
    people: list[ReferencePerson]
    sheet: str | None
    duplicate_rows: list[dict]
    user_id_column_present: bool
    columns: dict[str, str] = dataclass_field(default_factory=dict)


def saved_reference(report: Path, source_run=None):
    """Verify and reopen an existing comparison's frozen source/reference, never the current Excel file."""
    from .config import BenchmarkConfig

    identity = read_json(report / "identity.json")
    source = Path(source_run or identity["source_run"]).resolve()
    for name, expected in (("manifest.json", identity["manifest_sha256"]),
                           ("summary.json", identity["summary_sha256"])):
        if file_hash(source / name) != expected:
            raise ValueError("Quelllauf stimmt nicht mehr mit gespeichertem Vergleich überein")
    for method, expected in identity["extraction_sha256"].items():
        if expected and file_hash(source / method / "extractions.jsonl") != expected:
            raise ValueError("Historische Extraktionen wurden verändert")
    for path,key in ((report/"config.json","comparison_config_sha256"),(source/"config.yaml","source_config_sha256")):
        if identity.get(key) and file_hash(path) != identity[key]:
            raise ValueError("Eingefrorene Konfiguration wurde verändert")
    snapshot_path = report / "reference_snapshot.json"
    if identity.get("reference_snapshot_sha256") and file_hash(snapshot_path) != identity["reference_snapshot_sha256"]:
        raise ValueError("Eingefrorener Referenzsnapshot wurde verändert")
    snapshot = read_json(snapshot_path)
    data = ReferenceData([ReferencePerson(**p) for p in snapshot["people"]], identity.get("reference_sheet"),
                         snapshot.get("duplicate_rows", []), "user_id" in snapshot.get("columns", {}), snapshot.get("columns", {}))
    return (source, data, identity["reference_sha256"], Path(identity["reference_file"]),
            BenchmarkConfig.model_validate(read_json(report / "config.json")))


def column_indices(headers, config):
    return resolve_columns(headers, config.columns.model_dump(), optional=("user_id",))[0]


def status_indices(headers, config):
    result = {}
    for field, label in config.columns.model_dump().items():
        if field != "class_id":
            matches = [i for i, value in enumerate(headers) if value in (f"{label} – Status", f"{field}__state")]
            if len(matches) > 1:
                raise ValueError("Mehrdeutige Referenz-Statusspalten")
            if matches:
                result[field] = matches[0]
    return result


def read_reference(path: Path, config: ReferenceConfig) -> ReferenceData:
    records, sheet_title = [], None
    if path.suffix.lower() == ".csv":
        try:
            with path.open(encoding=config.encoding, newline="") as stream:
                sample = stream.read(65536)
                stream.seek(0)
                delimiter = config.delimiter
                if delimiter is None:
                    try:
                        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
                    except csv.Error:
                        raise ValueError("CSV-Trennzeichen unklar; reference.delimiter konfigurieren") from None
                reader = csv.reader(stream, delimiter=delimiter, strict=True)
                for _ in range(config.header_row - 1):
                    next(reader, None)
                headers = next(reader, [])
                indices, labels = resolve_columns(headers, config.columns.model_dump(), optional=("user_id",))
                states = status_indices(headers, config)
                for number, row in enumerate(reader, config.header_row + 1):
                    if not any(value.strip() for value in row):
                        continue
                    if max(indices.values()) >= len(row):
                        raise ValueError(f"CSV-Zeile {number} enthält zu wenige Spalten")
                    values = {field: row[index].strip() for field, index in indices.items()}
                    records.append(person(number, values, {field: row[i] if i < len(row) else "" for field, i in states.items()}))
        except UnicodeError:
            raise ValueError("CSV-Zeichenkodierung ungültig; UTF-8 exportieren oder reference.encoding angeben") from None
        except csv.Error:
            raise ValueError("CSV-Format ungültig; Trennzeichen und Anführungszeichen prüfen") from None
    elif path.suffix.lower() == ".xlsx":
        book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        try:
            if config.sheet and config.sheet not in book.sheetnames:
                raise ValueError("Das konfigurierte Excel-Blatt fehlt")
            sheet = book[config.sheet] if config.sheet else book.active
            sheet_title = sheet.title
            header = next(sheet.iter_rows(min_row=config.header_row, max_row=config.header_row), [])
            indices, labels = resolve_columns([cell.value for cell in header], config.columns.model_dump(), optional=("user_id",))
            states = status_indices([cell.value for cell in header], config)
            for number, row in enumerate(sheet.iter_rows(min_row=config.header_row + 1), config.header_row + 1):
                values = {field: cell_text(row[index], identifier=field in ("class_id", "user_id"))
                          for field, index in indices.items()}
                if any(values.values()):
                    records.append(person(number, values, {field: cell_text(row[i]) for field, i in states.items()}))
        finally:
            book.close()
    else:
        raise ValueError("Referenz muss eine .csv- oder .xlsx-Datei sein")
    if not records:
        raise ValueError("Keine Referenzteilnehmer gefunden")
    for record in records:
        if not config.usable_id(record.user_id) and not (record.first_name or record.last_name):
            raise ValueError(f"Keine lesbare Teilnehmeridentität in Referenzzeile {record.row_number}")
    groups = defaultdict(list)
    for record in records:
        key = tuple(tuple(sorted(value.items())) if isinstance(value, dict) else value
                    for name, value in asdict(record).items() if name != "row_number")
        groups[key].append(record)
    duplicates = [{"source_rows": [record.row_number for record in group], "copies": len(group)}
                  for group in groups.values() if len(group) > 1]
    if duplicates and not config.merge_identical_duplicates:
        raise ValueError("Identische Referenzzeilen vorhanden; bereinigen oder reference.merge_identical_duplicates aktivieren. "
                         "Erste betroffene Zeilen: " + ", ".join(map(str, duplicates[0]["source_rows"])))
    selected = [group[0] for group in groups.values()] if duplicates else records
    return ReferenceData(selected, sheet_title, duplicates, "user_id" in indices, labels)


def person(number, values, states=None):
    values.setdefault("user_id", "")
    if not values["class_id"]:
        raise ValueError(f"Schulungs-ID fehlt in Referenzzeile {number}")
    if not any(values.get(field) for field in ("user_id", "first_name", "last_name")):
        raise ValueError(f"Keine Teilnehmeridentität in Referenzzeile {number}")
    states = {field: value.strip().lower() for field, value in (states or {}).items() if value.strip()}
    if any(state not in ("read", "empty", "unknown", "masked", "illegible", "uncertain") for state in states.values()):
        raise ValueError(f"Ungültiger Referenzstatus in Zeile {number}")
    if any((state == "read" and not values.get(field)) or (state == "empty" and values.get(field))
           for field, state in states.items()):
        raise ValueError(f"Widersprüchlicher Referenzstatus in Zeile {number}")
    return ReferencePerson(row_number=number, field_states=states, **values)
