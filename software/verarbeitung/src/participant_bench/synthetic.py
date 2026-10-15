"""Synthetic public fixture, explicitly authored truth; never prefilled from model output."""

from pathlib import Path

import pymupdf
from PIL import Image

from .io import file_hash, write_json, write_jsonl
from .schema import Box, GroundTruthPage, Participant, TextField

ROWS = [("1", "Anna", "Weber", "00123", "Technik"), ("2", "Ben", "Fischer", "00007", "Verwaltung")]
WIDTH, HEIGHT = 595, 842
XS = [30, 65, 155, 255, 365, 465, 565]
YS = [145, 180, 230, 280]


def add_table(page, rows=True):
    page.insert_text((30, 75), "Teilnehmerliste - Synthetische Schulung", fontsize=17)
    headers = ["Nr", "Vorname", "Nachname", "Personalnummer", "Abteilung", "Unterschrift"]
    for x, text in zip(XS, headers):
        page.insert_text((x + 5, 166), text, fontsize=9)
    for x in XS:
        page.draw_line((x, YS[0]), (x, YS[-1]), width=0.7)
    for y in YS:
        page.draw_line((XS[0], y), (XS[-1], y), width=0.7)
    if rows:
        for index, row in enumerate(ROWS):
            for x, text in zip(XS, row):
                page.insert_text((x + 5, YS[index + 1] + 29), text, fontsize=12)
        # This is an ambiguous synthetic mark, NOT a positive training signature.
        page.draw_polyline([(477, 206), (485, 195), (491, 212), (502, 200), (514, 207)], width=1.5)


def participants():
    result = []
    for index, row in enumerate(ROWS):
        fields = {
            name: TextField(value=value, state="read")
            for name, value in zip(("first_name", "last_name", "personnel_number", "department"), row[1:])
        }
        result.append(
            Participant(
                row_ref=row[0],
                bbox=Box(x0=0.0, y0=YS[index + 1] / HEIGHT, x1=1.0, y1=YS[index + 2] / HEIGHT),
                **fields,
                signature_present=None if index == 0 else False,
                signature_state="uncertain" if index == 0 else "read",
                review_notes=["Synthetic stroke is deliberately not annotated as genuine signature"]
                if index == 0
                else [],
            )
        )
    return result


def generate(output: Path):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Synthetic output folder must be empty; refusing to overwrite")
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    add_table(document.new_page(width=WIDTH, height=HEIGHT))
    document.new_page(width=WIDTH, height=HEIGHT)
    title = document.new_page(width=WIDTH, height=HEIGHT)
    title.insert_text((60, 120), "Schulungsunterlagen", fontsize=25)
    title.insert_text((60, 170), "Dies ist ein Deckblatt ohne Teilnehmerdaten.", fontsize=14)
    add_table(document.new_page(width=WIDTH, height=HEIGHT), rows=False)
    rotated = document.new_page(width=WIDTH, height=HEIGHT)
    add_table(rotated)
    rotated.set_rotation(90)
    # Physically sideways scan without metadata, distinct from the preceding metadata case.
    original = document[0].get_pixmap(dpi=180, alpha=False)
    image = Image.frombytes("RGB", [original.width, original.height], original.samples).rotate(
        -90, expand=True
    )
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    scan = document.new_page(width=HEIGHT, height=WIDTH)
    scan.insert_image(scan.rect, stream=buffer.getvalue())
    pdf = raw / "synthetic.pdf"
    document.save(pdf)
    document.close()
    image.close()
    doc_id = file_hash(pdf)
    truth = []
    for page_number in range(1, 7):
        relevant = page_number in (1, 4, 5, 6)
        truth.append(
            GroundTruthPage(
                document_id=doc_id,
                page_number=page_number,
                split="development",
                dependency_group="synthetic-family-1",
                content_type="typed" if relevant else "other",
                relevant=relevant,
                participants=participants() if page_number in (1, 5, 6) else [],
            )
        )
    write_jsonl(output / "ground_truth.jsonl", [p.model_dump() for p in truth])
    write_json(
        output / "fixture_notes.json",
        {
            "document_id": doc_id,
            "curation": {
                "1": {"include": True, "total_additional_clockwise": 0},
                "2": {"include": False, "total_additional_clockwise": 0},
                "3": {"include": False, "total_additional_clockwise": 0},
                "4": {"include": True, "total_additional_clockwise": 0},
                "5": {"include": True, "total_additional_clockwise": 270},
                "6": {"include": True, "total_additional_clockwise": 270},
            },
            "note": "PyMuPDF applies the 90 degree metadata on page 5; viewer result is sideways. "
            "270 additional degrees restore portrait on pages 5 and 6. Truth boxes assume portrait. "
            "All annotations authored from fixture construction, not OCR/model output.",
        },
    )
    (raw / "skip-me.txt").write_text("Non-PDF input must be logged as skipped.", encoding="utf-8")
    return pdf
