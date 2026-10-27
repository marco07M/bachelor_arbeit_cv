"""Author a small multilingual table fixture independently of any OCR predictions."""

import argparse
from pathlib import Path

import pymupdf
import yaml

from participant_bench.config import load_config
from participant_bench.io import file_hash, write_csv, write_jsonl
from participant_bench.schema import GroundTruthPage, Participant, TextField

PEOPLE = [
    ("Zoë", "Groß-Müller", "", "XY/42"),
    ("Anne Marie", "D'Arcy", "00123", ""),
    ("Mika", "Weber", "00007", "AB-3"),
]


def generate(output):
    inputs = output / "pdf"
    inputs.mkdir(parents=True, exist_ok=False)
    images = output / "images"
    images.mkdir()
    path = inputs / "123456.pdf"
    with pymupdf.open() as document:
        for index in range(2):
            page = document.new_page(width=840, height=595)
            page.insert_text((45, 55), "Synthetische Teilnehmerliste / Synthetic participants", fontsize=17)
            bounds = [45, 80, 220, 410, 545, 680, 795]
            headings = ["Nr.", "Vorname", "Nachname", "Benutzer", "Kurzzeichen", "Unterschrift"]
            for row in range(5):
                y = 100 + row * 65
                page.draw_line((bounds[0], y), (bounds[-1], y), width=1)
            for x in bounds:
                page.draw_line((x, 100), (x, 360), width=1)
            for column, value in enumerate(headings):
                page.insert_text((bounds[column] + 7, 135), value, fontsize=12)
            for row, values in enumerate(PEOPLE, 1):
                for column, value in enumerate([str(row), *values, ""]):
                    if value:
                        page.insert_text((bounds[column] + 7, 135 + row * 65), value, fontsize=13)
            if index:
                page.set_rotation(90)
        document.save(path)
        document[0].get_pixmap(dpi=150).save(images / "123456.png")
    document_id = file_hash(path)
    participants = [
        Participant(
            row_ref=str(index),
            first_name=TextField(value=values[0], state="read"),
            last_name=TextField(value=values[1], state="read"),
            personnel_number=TextField(value=values[2], state="read" if values[2] else "empty"),
            department=TextField(value=values[3], state="read" if values[3] else "empty"),
        )
        for index, values in enumerate(PEOPLE, 1)
    ]
    truth = [
        GroundTruthPage(
            document_id=document_id,
            page_number=number,
            split="development",
            dependency_group="authored-smoke",
            content_type="typed",
            relevant=True,
            participants=participants,
        )
        for number in (1, 2)
    ]
    write_jsonl(output / "ground_truth.jsonl", [page.model_dump() for page in truth])
    references = output / "reference"
    references.mkdir()
    transcript = (
        "Synthetische Teilnehmerliste / Synthetic participants\n"
        + "Nr. Vorname Nachname Benutzer Kurzzeichen Unterschrift\n"
    )
    transcript += "\n".join(" ".join([str(index), *values]) for index, values in enumerate(PEOPLE, 1))
    (references / "page.txt").write_text(transcript, encoding="utf-8")
    write_csv(
        references / "pages.csv",
        [
            dict(
                document_id=document_id,
                page_number=number,
                text_reviewed="true",
                reference_text_file="page.txt",
            )
            for number in (1, 2)
        ]
        + [
            dict(
                document_id=file_hash(images / "123456.png"),
                page_number=1,
                text_reviewed="true",
                reference_text_file="page.txt",
            )
        ],
    )
    config = load_config(Path("configs/unlimited-ocr-table.yaml"))
    config.methods = ["ocr_rules", "unlimited_ocr"]
    (output / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(), allow_unicode=True), encoding="utf-8"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/unlimited-smoke"))
    print(generate(parser.parse_args().output))
