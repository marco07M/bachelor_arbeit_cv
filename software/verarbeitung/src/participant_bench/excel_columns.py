"""Resolve reference columns without replacing their original display names."""

from .evaluation import normalized


def resolve_columns(headers, columns, *, optional=()):
    names = [str(value) if value is not None else "" for value in headers]
    keys = [normalized(name, "name") for name in names]
    indices = {}
    for field, title in columns.items():
        matches = [index for index, name in enumerate(keys) if name == normalized(title, "name")]
        if not matches and field in optional:
            continue
        if len(matches) != 1:
            raise ValueError(f"Referenzspalte {title!r} muss genau einmal vorhanden sein")
        indices[field] = matches[0]
    if len(set(indices.values())) != len(indices):
        raise ValueError("Jedes Referenzfeld benötigt eine eigene Spalte")
    labels = {field: names[index] for field, index in sorted(indices.items(), key=lambda item: item[1])}
    return indices, labels


def field_labels(columns=None):
    from .excel_reference import ExcelColumns

    labels = ExcelColumns().model_dump()
    labels.update(columns or {})
    labels["personnel_number"] = labels["user_id"]
    labels["department"] = labels["short_code"]
    return labels


def write_participants_xlsx(path, groups, columns=None, *, references=None):
    """One sheet per method with reference headings; source locations live on a separate sheet."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell

    from .excel_reference import ExcelColumns

    titles = dict(columns or ExcelColumns().model_dump())
    book = Workbook(write_only=True)
    source_rows = []

    def append(sheet, values):
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"  # IDs keep zeroes; OCR values are never Excel formulas.
            cells.append(cell)
        sheet.append(cells)

    for method, records in groups.items():
        sheet = book.create_sheet(method)
        append(sheet, titles.values())
        for number, record in enumerate(records, 2):
            append(sheet, [record.get(field) for field in titles])
            source_rows.append([method, number, record.get("source_file"), record.get("document_id"),
                                record.get("page_number"), record.get("output_index"), None])
    if references is not None:
        sheet = book.create_sheet("Referenz")
        append(sheet, titles.values())
        for number, record in enumerate(references, 2):
            append(sheet, [getattr(record, field) for field in titles])
            source_rows.append(["Referenz", number, None, None, None, None, record.row_number])
    source = book.create_sheet("Quellen")
    append(source, ["Blatt", "Excel-Zeile", "Datei", "Dokument-ID", "PDF-Seite", "Eintragsindex", "Referenzzeile"])
    for row in source_rows:
        append(source, row)
    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
