"""Conservative table extraction: keep observed cells and their source rows, never complete names."""

import re
from html.parser import HTMLParser

from .schema import TEXT_FIELDS, Participant, TextField

HEADERS = {
    "first_name": {"vorname", "firstname", "vornamen"},
    "last_name": {"name", "nachname", "lastname", "familienname", "surname"},
    "personnel_number": {
        "benutzer",
        "benutzerid",
        "userid",
        "personalnummer",
        "personalnr",
        "personnelnumber",
    },
    "department": {"kurzzeichen", "abteilung", "department", "organization", "organisation"},
    "row_ref": {"nr", "lfd", "nummer", "no"},
}


def clean_text(raw: str) -> str:
    """Remove format markers, retaining table markup and observed spelling."""
    text = re.sub(r"<\|det\|>[^<]*<\|/det\|>", "\n", raw)
    return re.sub(r"<\|(?:endoftext|eot_id)\|>|<｜(?:end▁of▁sentence|begin▁of▁sentence)｜>", "", text).strip()


def label(value):
    return re.sub(r"[^a-zäöüß]", "", value.casefold())


def markdown_cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if re.search(r"(?<!\\)\|$", line):
        line = line[:-1]
    return re.split(r"(?<!\\)\|", line)


def plain_text(text):
    """Derive a separate reading-order transcript; table markup remains in clean_text."""

    class Transcript(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

        def handle_starttag(self, tag, attrs):
            if tag in ("tr", "p", "br", "table"):
                self.parts.append("\n")
            elif tag in ("td", "th"):
                self.parts.append("\t")

    if "<table" in text.lower():
        parser = Transcript()
        parser.feed(text)
        return "".join(parser.parts).strip()
    lines = []
    for line in text.splitlines():
        if line.count("|") >= 2:
            cells = markdown_cells(line)
            if all(re.fullmatch(r"\s*:?-+:?\s*", cell) for cell in cells):
                continue
            line = "\t".join(cell.strip().replace(r"\|", "|") for cell in cells)
        lines.append(line)
    return "\n".join(lines)


class HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.row, self.cell = [], None, None, None
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.rows is not None:
                self.invalid = True
            else:
                self.rows, self.invalid = [], False
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            if any(k in ("rowspan", "colspan") and v != "1" for k, v in attrs):
                self.invalid = True  # Do not guess the positions of merged cells.
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.rows is not None and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.rows is not None:
            self.tables.append((self.rows, self.invalid))
            self.rows, self.row, self.cell = None, None, None


def tables(text):
    if "<table" in text.lower():
        parser = HTMLTables()
        parser.feed(text)
        return parser.tables
    output, current = [], []
    for line in text.splitlines() + [""]:
        if line.count("|") >= 2:
            cells = markdown_cells(line)
            if not all(re.fullmatch(r"\s*:?-+:?\s*", cell) for cell in cells):
                current.append([cell.replace(r"\|", "|") for cell in cells])
        elif current:
            output.append((current, False))
            current = []
    return output


def extract_tables(text):
    participants, evidence, notes = [], [], []
    for table_index, (rows, invalid) in enumerate(tables(text)):
        if invalid:
            notes.append(f"Tabelle {table_index}: verbundene oder verschachtelte Zellen; Zuordnung prüfen")
            continue
        mapping, header_index = {}, None
        for index, cells in enumerate(rows):
            found = {
                field: [i for i, cell in enumerate(cells) if label(cell) in names]
                for field, names in HEADERS.items()
            }
            if any(len(indices) > 1 for indices in found.values()):
                continue
            candidate = {field: indices[0] for field, indices in found.items() if indices}
            if len(set(candidate) & set(TEXT_FIELDS)) >= 2 and set(candidate) & {"first_name", "last_name"}:
                mapping, header_index = candidate, index
                break
        if header_index is None:
            notes.append(f"Tabelle {table_index}: keine eindeutige Feldzuordnung; Rohtext erhalten")
            continue
        width = len(rows[header_index])
        for row_index, cells in enumerate(rows[header_index + 1 :], header_index + 1):
            if len(cells) != width:
                notes.append(
                    f"Tabelle {table_index}, Zeile {row_index}: abweichende Zellzahl; keine Verschiebung geraten"
                )
                continue
            if all(label(cells[index]) in HEADERS[field] for field, index in mapping.items()):
                continue  # Repeated column headings, not a participant.
            values = {name: " ".join(cells[index].split()) for name, index in mapping.items()}
            if not any(values.get(name) for name in TEXT_FIELDS):
                continue
            fields = {
                name: TextField(value=values[name], state="read" if values[name] else "empty")
                if name in values
                else TextField(state="uncertain")
                for name in TEXT_FIELDS
            }
            ref = values.get("row_ref")
            if ref and not re.fullmatch(r"\d+", ref):
                ref = None
            participants.append(
                Participant(
                    **fields,
                    row_ref=ref,
                    signature_present=None,
                    signature_state="uncertain",
                    review_notes=[
                        "Felder aus OCR-Tabellenzellen; Schreibweise und Zeilenzuordnung manuell prüfen. "
                        "Keine Unterschriftenentscheidung aus OCR-Text."
                    ],
                )
            )
            evidence.append(
                dict(
                    output_index=len(participants) - 1,
                    table_index=table_index,
                    source_row_index=row_index,
                    column_mapping=mapping,
                    raw_cells=cells,
                )
            )
    if not participants:
        notes.append(
            "Keine Teilnehmer eindeutig aus Tabellenzellen zugeordnet; vollständiger OCR-Text bleibt erhalten"
        )
    return participants, evidence, notes
