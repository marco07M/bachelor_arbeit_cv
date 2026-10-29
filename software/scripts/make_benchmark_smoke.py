"""Create a small, independently specified synthetic PDF and reference; no model downloads."""

import argparse
import csv
from pathlib import Path

import pymupdf

from participant_bench.io import file_hash, write_jsonl
from participant_bench.schema import GroundTruthPage, VisualParticipant


def generate(root: Path):
    root.mkdir(parents=True, exist_ok=False)
    raw = root / "pdfs"
    raw.mkdir()
    values = [("Max", "Muster", "000007", "ABC-12"), ("Nora", "Fischer", "000008", "XYZ")]
    with pymupdf.open() as document:
        page = document.new_page(width=842, height=595)
        page.insert_text((40, 55), "Teilnehmerliste - ausschliesslich synthetische Personen", fontsize=16)
        xs, ys = [40, 80, 210, 380, 510, 650, 800], [95, 135, 180, 225]
        for x in xs:
            page.draw_line((x, ys[0]), (x, ys[-1]))
        for y in ys:
            page.draw_line((xs[0], y), (xs[-1], y))
        rows = [["Nr", "Vorname", "Nachname", "Benutzer", "Kurzzeichen", "Unterschrift"],
                *[[str(i+1), *person, ""] for i, person in enumerate(values)]]
        for i, row in enumerate(rows):
            for j, text in enumerate(row):
                page.insert_text((xs[j]+6, ys[i]+26), text, fontsize=12)
        document.save(raw / "123456.pdf")
    document_id = file_hash(raw / "123456.pdf")
    people = [VisualParticipant(row_ref=str(i+1), first_name=first, last_name=last, personnel_number=user,
        department=code, signature_present=False).participant()
        for i, (first, last, user, code) in enumerate(values)]
    truth = GroundTruthPage(document_id=document_id, page_number=1, split="development",
        dependency_group=document_id, content_type="typed", relevant=True, participants=people)
    write_jsonl(root / "ground_truth.jsonl", [truth.model_dump()])
    with (root / "reference.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows(["123456", user, first, last, code] for first, last, user, code in values)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    print(generate(parser.parse_args().output))
