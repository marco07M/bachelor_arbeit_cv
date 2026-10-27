"""Create authored, synthetic grouped references to exercise calibration CLI without real data."""

import argparse
import itertools
from pathlib import Path

import pymupdf
import yaml

from participant_bench.calibration.dataset import initialize, rows, split_dataset
from participant_bench.config import load_config
from participant_bench.io import read_json, write_csv
from participant_bench.synthetic import ROWS


def generate(output: Path, groups=10):
    if output.exists() or not 5 <= groups <= 24:
        raise ValueError("Use a new output folder and 5..24 synthetic layout groups")
    raw = output / "raw"
    raw.mkdir(parents=True)
    orders = list(itertools.permutations((1, 2, 3, 4)))
    xs, ys = [30, 65, 165, 265, 365, 465, 565], [145, 180, 230, 280]
    labels = ["Nr", "Vorname", "Nachname", "Personalnummer", "Abteilung"]
    texts = {}
    for family in range(groups):
        order = (0,) + orders[family]
        for copy in range(2):
            filename = f"f{family:02d}-{copy}.pdf"
            title = f"Synthetic calibration layout {family:02d} copy {copy}"
            lines = [title, " ".join(labels[i] for i in order) + " Unterschrift"]
            with pymupdf.open() as document:
                page = document.new_page(width=595, height=842)
                page.insert_text((30, 75), title, fontsize=14)
                for x in xs:
                    page.draw_line((x, ys[0]), (x, ys[-1]), width=0.7)
                for y in ys:
                    page.draw_line((xs[0], y), (xs[-1], y), width=0.7)
                for x, index in zip(xs, order):
                    page.insert_text((x + 4, 166), labels[index], fontsize=9)
                page.insert_text((xs[-2] + 4, 166), "Unterschrift", fontsize=9)
                for j, row in enumerate(ROWS):
                    lines.append(" ".join(row[i] for i in order))
                    for x, index in zip(xs, order):
                        page.insert_text((x + 4, ys[j + 1] + 29), row[index], fontsize=11)
                document.save(raw / filename)
            texts[filename] = "\n".join(lines)
    reference = initialize(raw, output / "reference")
    inventory = {d["document_id"]: d for d in read_json(reference / "dataset.json")["documents"]}
    documents = rows(reference / "documents.csv")
    for document in documents:
        family = Path(inventory[document["document_id"]]["path"]).stem.split("-")[0]
        document.update(dependency_group=family, grouping_reviewed="true", stratum="synthetic-typed")
    write_csv(reference / "documents.csv", documents)
    pages, people = rows(reference / "pages.csv"), []
    for page in pages:
        page.update(reviewed="true", text_reviewed="true")
        filename = inventory[page["document_id"]]["path"]
        (reference / page["reference_text_file"]).write_text(texts[filename], encoding="utf-8")
        for row in ROWS:
            person = dict(
                document_id=page["document_id"],
                page_number=1,
                row_ref=row[0],
                bbox="",
                signature_present="unknown",
            )
            for field, value in zip(("first_name", "last_name", "personnel_number", "department"), row[1:]):
                person[field], person[field + "_state"] = value, "read"
            people.append(person)
    write_csv(reference / "pages.csv", pages)
    write_csv(reference / "participants.csv", people)
    split_dataset(reference)
    base = load_config(Path(__file__).resolve().parents[1] / "configs/smoke.yaml")
    base.pdf.auto_orient = False
    (output / "base.yaml").write_text(yaml.safe_dump(base.model_dump()), encoding="utf-8")
    (output / "experiment.yaml").write_text(
        yaml.safe_dump(
            dict(
                base_config="base.yaml",
                variants=[dict(name="pdf_text", overrides=dict(ocr=dict(source="prefer_pdf")))],
            )
        ),
        encoding="utf-8",
    )
    print(f"Synthetic references: {reference}; experiment config: {output / 'experiment.yaml'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/calibration-smoke"))
    parser.add_argument("--groups", type=int, default=10)
    args = parser.parse_args()
    generate(args.output, args.groups)
