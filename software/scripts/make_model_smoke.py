"""Create a tiny one-page model smoke fixture with manually authored synthetic truth."""

from pathlib import Path

import pymupdf

from participant_bench.io import file_hash, write_jsonl
from participant_bench.schema import GroundTruthPage
from participant_bench.synthetic import HEIGHT, WIDTH, add_table, participants

output = Path("data/model-smoke")
output.mkdir(parents=True, exist_ok=True)
raw = output / "raw"
raw.mkdir(exist_ok=True)
pdf = raw / "two-participants.pdf"
if pdf.exists():
    raise SystemExit("Fixture already exists; no overwrite")
doc = pymupdf.open()
add_table(doc.new_page(width=WIDTH, height=HEIGHT))
doc.save(pdf)
doc.close()
truth = GroundTruthPage(
    document_id=file_hash(pdf),
    page_number=1,
    split="development",
    dependency_group="synthetic-model-smoke",
    content_type="typed",
    relevant=True,
    participants=participants(),
)
write_jsonl(output / "ground_truth.jsonl", [truth.model_dump()])
print(raw)
