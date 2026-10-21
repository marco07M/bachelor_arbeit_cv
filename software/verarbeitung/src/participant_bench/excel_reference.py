"""Read the local course roster without passing reference data to extractors."""

import math
import re
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile

import yaml
from openpyxl import load_workbook
from pydantic import Field, field_validator

from .config import ConfigModel
from .evaluation import normalized


class ExcelColumns(ConfigModel):
    class_id: str = "Class ID"
    user_id: str = "User ID"
    first_name: str = "First Name"
    last_name: str = "Last Name"
    short_code: str = "Organization"


class ExcelConfig(ConfigModel):
    columns: ExcelColumns = Field(default_factory=ExcelColumns)
    sheet: str | None = None
    header_row: int = Field(default=1, ge=1)
    masked_user_id_pattern: str = r"(?i)([*#?●█■•×]|x{2,}|geschwärzt|geschwaerzt|redacted|masked|unkenntlich)"
    missing_user_ids: list[str] = Field(default_factory=lambda: ["n/a", "na", "null", "unknown", "unbekannt", "-"])

    @field_validator("masked_user_id_pattern")
    @classmethod
    def valid_pattern(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"Ungültiges Maskierungs-Muster: {exc}") from exc
        return value

    def usable_id(self, value: str | None) -> bool:
        return bool(value and value.strip()) and (
            normalized(value, "name") not in {normalized(v, "name") for v in self.missing_user_ids}
            and re.search(self.masked_user_id_pattern, value) is None
        )


@dataclass(frozen=True)
class ReferencePerson:
    row_number: int
    class_id: str
    user_id: str
    first_name: str
    last_name: str
    short_code: str

    @property
    def name_key(self) -> tuple[str, str, str] | None:
        values = (self.first_name, self.last_name, self.short_code)
        return tuple(normalized(v, "name") for v in values) if all(v.strip() for v in values) else None


def load_excel_config(path: Path | None) -> ExcelConfig:
    return ExcelConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path else ExcelConfig()


def cell_text(cell, *, identifier: bool = False) -> str:
    value = cell.value
    if value is None:
        return ""
    if cell.data_type == "f":
        raise ValueError(f"Formel in Referenzzelle {cell.coordinate}; bitte als feste Werte exportieren")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        raise ValueError(f"Boolescher Wert in Referenzzelle {cell.coordinate}")
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value != int(value):
            raise ValueError(f"Keine ganzzahlige Referenz in Zelle {cell.coordinate}")
        text = str(int(value))
        if identifier:
            if len(text.lstrip("-")) > 15:
                raise ValueError(f"ID in {cell.coordinate} bitte als Text speichern (Excel-Zahlengenauigkeit)")
            if re.fullmatch(r"0+", cell.number_format):
                text = text.zfill(len(cell.number_format))
            elif cell.number_format != "General":
                raise ValueError(f"ID-Zahlenformat in {cell.coordinate} nicht unterstützt; ID als Text speichern")
        return text
    raise ValueError(f"Nicht unterstützter Zelltyp in {cell.coordinate}; bitte als Text exportieren")


def read_reference(path: Path, config: ExcelConfig) -> tuple[list[ReferencePerson], str]:
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Excel-Referenz bitte im Format .xlsx bereitstellen")
    try:
        workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    except BadZipFile as exc:
        raise ValueError("Excel-Datei ist beschädigt oder keine gültige .xlsx-Datei") from exc
    try:
        if config.sheet and config.sheet not in workbook.sheetnames:
            raise ValueError(f"Excel-Blatt fehlt: {config.sheet}; vorhanden: {workbook.sheetnames}")
        sheet = workbook[config.sheet] if config.sheet else workbook.active
        headers = next(sheet.iter_rows(min_row=config.header_row, max_row=config.header_row), ())
        names = [normalized(str(cell.value or ""), "name") for cell in headers]
        indices = {}
        for field, title in config.columns.model_dump().items():
            matches = [i for i, name in enumerate(names) if name == normalized(title, "name")]
            if len(matches) != 1:
                raise ValueError(f"Excel-Spalte {title!r} muss genau einmal vorhanden sein")
            indices[field] = matches[0]
        records = []
        for number, row in enumerate(sheet.iter_rows(min_row=config.header_row + 1), config.header_row + 1):
            values = {
                field: cell_text(row[index], identifier=field in ("class_id", "user_id"))
                for field, index in indices.items()
            }
            if not any(values.values()):
                continue
            if not values["class_id"]:
                raise ValueError(f"Class ID fehlt in Excel-Zeile {number}")
            records.append(ReferencePerson(row_number=number, **values))
        if not records:
            raise ValueError("Excel enthält keine Referenzeinträge")
        return records, sheet.title
    finally:
        workbook.close()
