"""Stream XLSX/CSV reference columns as strings; preserve identifiers and original source row numbers."""

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from ..excel_columns import resolve_columns
from ..excel_reference import ReferencePerson, cell_text
from .config import ReferenceConfig


@dataclass
class ReferenceData:
    people: list[ReferencePerson]
    sheet: str | None
    duplicate_rows: list[dict]
    user_id_column_present: bool
    columns: dict[str, str] = field(default_factory=dict)


def column_indices(headers, config):
    return resolve_columns(headers, config.columns.model_dump(), optional=("user_id",))[0]


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
                indices, labels = resolve_columns(next(reader, []), config.columns.model_dump(), optional=("user_id",))
                for number, row in enumerate(reader, config.header_row + 1):
                    if not any(value.strip() for value in row):
                        continue
                    if max(indices.values()) >= len(row):
                        raise ValueError(f"CSV-Zeile {number} enthält zu wenige Spalten")
                    values = {field: row[index].strip() for field, index in indices.items()}
                    records.append(person(number, values))
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
            for number, row in enumerate(sheet.iter_rows(min_row=config.header_row + 1), config.header_row + 1):
                values = {field: cell_text(row[index], identifier=field in ("class_id", "user_id"))
                          for field, index in indices.items()}
                if any(values.values()):
                    records.append(person(number, values))
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
        key = tuple(value for name, value in asdict(record).items() if name != "row_number")
        groups[key].append(record)
    duplicates = [{"source_rows": [record.row_number for record in group], "copies": len(group)}
                  for group in groups.values() if len(group) > 1]
    if duplicates and not config.merge_identical_duplicates:
        raise ValueError("Identische Referenzzeilen vorhanden; bereinigen oder reference.merge_identical_duplicates aktivieren. "
                         "Erste betroffene Zeilen: " + ", ".join(map(str, duplicates[0]["source_rows"])))
    selected = [group[0] for group in groups.values()] if duplicates else records
    return ReferenceData(selected, sheet_title, duplicates, "user_id" in indices, labels)


def person(number, values):
    values.setdefault("user_id", "")
    if not values["class_id"]:
        raise ValueError(f"Schulungs-ID fehlt in Referenzzeile {number}")
    if not any(values.get(field) for field in ("user_id", "first_name", "last_name")):
        raise ValueError(f"Keine Teilnehmeridentität in Referenzzeile {number}")
    return ReferencePerson(row_number=number, **values)
