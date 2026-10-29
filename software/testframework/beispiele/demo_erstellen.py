"""Synthetic PDFs/roster and explicitly artificial predictions; no actual model inference or company data."""

import argparse
import csv
from pathlib import Path

import pymupdf

from participant_bench.io import file_hash, write_json, write_jsonl
from participant_bench.schema import PageResult, VisualParticipant

ROSTER = [
    ["123456", "001234", "Anna", "Weber", "MUC"],
    ["123456", "", "Jörg", "Groß-Müller", "BER"],
    ["654321", "000789", "Lea", "Schmidt", "ABC-12"],
]


def generate(root):
    root.mkdir(parents=True, exist_ok=False)
    inputs = root / "pdfs"
    inputs.mkdir()
    inventory, pages = [], []
    for course in sorted({row[0] for row in ROSTER}):
        rows = [row for row in ROSTER if row[0] == course]
        source = inputs / f"{course}.pdf"
        with pymupdf.open() as document:
            page = document.new_page(width=842, height=595)
            page.insert_text((40, 45), f"Synthetische Teilnehmerliste - Schulung {course}", fontsize=16)
            columns = [40, 160, 340, 470, 610, 800]
            bottom = 100 + 50 * (len(rows) + 1)
            for x in columns:
                page.draw_line((x, 100), (x, bottom))
            for y in range(100, bottom + 1, 50):
                page.draw_line((40, y), (800, y))
            table = [["Vorname", "Nachname", "Benutzer", "Kurzzeichen", "Unterschrift"]]
            table.extend([first, last, user, code, ""] for _, user, first, last, code in rows)
            for number, cells in enumerate(table):
                for column, text in enumerate(cells):
                    page.insert_text((columns[column] + 8, 130 + 50 * number), text, fontsize=12)
            document.save(source)
        document_id = file_hash(source)
        inventory.append(dict(path=str(source.resolve()), kind="pdf", sha256=document_id))
        people = []
        for _, user, first, last, code in reversed(rows):
            people.append(VisualParticipant(first_name="Anma" if first == "Anna" else first,
                last_name=last, personnel_number=user or None, department=code, signature_present=None).participant())
        if course == "123456":
            people.append(people[-1].model_copy(deep=True))  # deliberate duplicate: one reference cannot score twice
        pages.append(PageResult(run_id="SYNTHETIC-NO-MODEL", document_id=document_id,
                     page_id=f"{document_id}-p0001", page_number=1, method_id="vlm", status="partial",
                     parse_status="valid", participants=people))
    reference = root / "referenz.csv"
    with reference.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows(reversed(ROSTER))
        writer.writerow(["999999", "009999", "Nicht", "Verarbeitet", "TEST"])
    saved = root / "synthetische_vorhersagen"
    write_json(saved / "manifest.json", dict(inputs=inventory))
    write_json(saved / "summary.json", {"vlm": dict(status="synthetic_fixture", output_kind="structured",
                                                    synthetic_predictions=True)})
    write_jsonl(saved / "vlm/extractions.jsonl", [page.model_dump() for page in pages])
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "generiert")
    print(generate(parser.parse_args().output).resolve())
