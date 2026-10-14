"""Fixture-only curation by construction notes, not by predictions/ground truth."""

import argparse
from pathlib import Path

from participant_bench.io import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--manifest", type=Path, default=Path("prepared/synthetic/manifest.json"))
parser.add_argument("--notes", type=Path, default=Path("data/synthetic/fixture_notes.json"))
args = parser.parse_args()
manifest, notes = read_json(args.manifest), read_json(args.notes)
for page in manifest["pages"]:
    if page["document_id"] != notes["document_id"]:
        raise ValueError("Only this synthetic fixture may be curated automatically")
    annotation = notes["curation"][str(page["page_number"])]
    page["include"] = annotation["include"]
    page["curation_rotation_clockwise"] = (
        annotation["total_additional_clockwise"] - page["additional_rotation_clockwise"]
    ) % 360
    page["curation_note"] = "Synthetic construction notes; no model-output-derived labels"
    page["review_required"] = False
    page["split"] = "development"
manifest["curated"] = True
write_json(args.manifest.with_name("curated.json"), manifest)
print(args.manifest.with_name("curated.json"))
