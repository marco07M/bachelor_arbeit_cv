"""Author synthetic tables with fixed columns and missing user IDs; never use real documents."""

import argparse
from pathlib import Path

import pymupdf

from participant_bench.io import file_hash, write_jsonl
from participant_bench.schema import GroundTruthPage, Participant, TextField

# Every expected field is authored here, independently of model output.
ROWS = [
    ("1", "Anna", "Weber", "", "FG-123"),
    ("2", "Ben", "Fischer", "00007", "IT/42"),
    ("3", "Nora", "Schmidt", "", "123/45"),
    ("4", "Leo", "Koch", "u00456", ""),
    ("5", "Mira", "Hahn", "", ""),
]


def generate(output: Path) -> Path:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty; existing documents are never overwritten")
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    pdf = raw / "123456.pdf"
    xs = [25, 58, 150, 250, 355, 455, 570]
    with pymupdf.open() as document:
        for order in ((0, 1, 2, 3, 4), (0, 3, 4, 2, 1)):
            page = document.new_page(width=595, height=842)
            page.insert_text((25, 55), "Synthetischer Spaltentest - Class ID: 123456", fontsize=14)
            labels = ("Nr", "Vorname", "Nachname", "Benutzer", "Kurzzeichen")
            for x, index in zip(xs, order):
                page.insert_text((x + 4, 120), labels[index], fontsize=10)
            page.insert_text((xs[-2] + 4, 120), "Unterschrift", fontsize=9)
            for x in xs:
                page.draw_line((x, 98), (x, 390), width=0.7)
            for y in (98, 140, 190, 240, 290, 340, 390):
                page.draw_line((xs[0], y), (xs[-1], y), width=0.7)
            for row_number, row in enumerate(ROWS):
                for x, index in zip(xs, order):
                    if row[index]:
                        page.insert_text((x + 4, 172 + 50 * row_number), row[index], fontsize=11)
        document.save(pdf)
    people = [
        Participant(
            row_ref=row[0],
            **{
                name: TextField(value=value, state="read" if value else "empty")
                for name, value in zip(("first_name", "last_name", "personnel_number", "department"), row[1:])
            },
        )
        for row in ROWS
    ]
    write_jsonl(
        output / "ground_truth.jsonl",
        [
            GroundTruthPage(
                document_id=file_hash(pdf),
                page_number=number,
                split="development",
                dependency_group="synthetic-empty-user",
                content_type="typed",
                relevant=True,
                participants=people,
            ).model_dump()
            for number in (1, 2)
        ],
    )
    return pdf


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/empty-user-smoke"))
    print(generate(parser.parse_args().output))
