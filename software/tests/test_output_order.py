"""Attendance order survives reversed reference lists and shuffled page serialization."""

import csv
from html.parser import HTMLParser

import pytest
from openpyxl import Workbook, load_workbook

from participant_bench.excel_comparison import compare_run
from participant_bench.excel_reference import ExcelConfig
from participant_bench.io import file_hash, write_json, write_jsonl
from participant_bench.report import report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.schema import PageResult, VisualParticipant


class SourceRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag in ("article", "tr") and "data-output-index" in data:
            self.rows.append(
                tuple(data.get(k, "") for k in ("data-document", "data-page", "data-output-index"))
            )


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def make_page(doc, number, people):
    return PageResult(
        run_id="fixture",
        document_id=doc,
        page_number=number,
        page_id=f"{doc}-p{number:04d}",
        method_id="vlm",
        status="success",
        parse_status="valid",
        participants=[
            VisualParticipant(
                first_name=first, last_name=last, personnel_number=uid, department=org
            ).participant()
            for first, last, uid, org in people
        ],
    )


@pytest.mark.parametrize("comparison", ["benchmark", "strict"])
def test_all_exports_follow_pdf_page_and_row_order_even_when_reference_is_reversed(tmp_path, comparison):
    source = tmp_path / "source"
    data = [
        ("Ben", "Lange", "0007", "A"),
        ("Xenia", "Zusatz", "0099", "EXTRA"),
        ("Anna", "Weber", "0008", "B"),
        ("Carla", "Kurz", "0009", "C"),
        ("Dora", "Berg", "0010", "D"),
        ("Elif", "Meyer", "0011", "E"),
    ]
    inputs = [
        dict(kind="pdf", sha256=doc, path=filename)
        for doc, filename in [("zdoc", "123456.pdf"), ("adoc", "456789.pdf"), ("mdoc", "123456__2.pdf")]
    ]
    write_json(source / "manifest.json", dict(inputs=inputs))
    write_json(source / "summary.json", {"vlm": dict(status="success", output_kind="structured")})
    pages = [
        make_page("mdoc", 1, [data[5]]),
        make_page("adoc", 1, [data[4]]),
        make_page("zdoc", 2, [data[3]]),
        make_page("zdoc", 1, data[:3]),
    ]
    extraction = source / "vlm/extractions.jsonl"
    write_jsonl(extraction, [p.model_dump() for p in pages])
    original_hash = file_hash(extraction)
    reference = tmp_path / "reference.xlsx"
    references = [("123456", *row) for i, row in enumerate(data) if i not in (1, 4)]
    references.append(("456789", *data[4]))
    references.append(("123456", "Fritz", "Fehlend", "0088", "REFONLY"))
    scores = []
    expected = [
        ("zdoc", "1", "0"),
        ("zdoc", "1", "1"),
        ("zdoc", "1", "2"),
        ("zdoc", "2", "0"),
        ("adoc", "1", "0"),
        ("mdoc", "1", "0"),
    ]
    for pass_index, records in enumerate((references, list(reversed(references)))):
        reference_book = Workbook()
        reference_book.active.append(["Class ID", "First Name", "Last Name", "User ID", "Organization"])
        for record in records:
            reference_book.active.append(record)
        reference_book.save(reference)
        reference_book.close()
        if comparison == "benchmark":
            output, score = evaluate_run(source, reference, BenchmarkConfig(), tmp_path / f"out{pass_index}")
            audit = csv_rows(output / "participants.csv")
            index_field = "output_index"
        else:
            output, score = compare_run(
                source, reference, ExcelConfig(), output=tmp_path / f"out{pass_index}"
            )
            audit = csv_rows(output / "matches.csv")
            index_field = "prediction_index"
        scores.append(score)
        located = [(r["document_id"], r["page_number"], r[index_field]) for r in audit if r["document_id"]]
        assert located == expected
        assert audit[-1]["status"] == "missing"
        book = load_workbook(output / "participants.xlsx", read_only=True)
        try:
            headers, *values = list(book["vlm"].values)
            assert [dict(zip(headers, row))["First Name"] for row in values] == [r[0] for r in data]
            assert [
                (r[3], str(r[4]), str(r[5])) for r in list(book["Quellen"].values)[1:] if r[0] == "vlm"
            ] == expected
        finally:
            book.close()
        if comparison == "benchmark":
            parser = SourceRows()
            parser.feed((output / "zuordnungen.html").read_text(encoding="utf-8"))
            assert [r for r in parser.rows if r[0]] == expected
            for detail in (output / "details").glob("*.html"):
                parser = SourceRows()
                parser.feed(detail.read_text(encoding="utf-8"))
                found = [r for r in parser.rows if r[0]]
                assert found == [r for r in expected if r in found]
                if any(not r[0] for r in parser.rows):
                    assert "Nur in der Referenz vorhanden" in detail.read_text(encoding="utf-8")
                    assert not parser.rows[-1][0]
        assert file_hash(extraction) == original_hash
    assert scores[0] == scores[1]


def test_raw_report_sorts_pages_without_reordering_their_participants(tmp_path):
    from test_excel_columns import source_run

    first, summary, manifest = source_run(tmp_path)
    second = make_page("document", 2, [("Ben", "Lange", "0008", "ABC")])
    manifest["pages"].append(dict(manifest["pages"][0], page_id=second.page_id, page_number=2))
    report(tmp_path, summary, {"vlm": [second, first]}, {}, manifest, {})
    book = load_workbook(tmp_path / "participants.xlsx", read_only=True)
    try:
        headers, *rows = list(book["vlm"].values)
        assert [dict(zip(headers, row))["First Name"] for row in rows] == ["Anna", "Ben"]
    finally:
        book.close()


def test_hybrid_field_export_uses_source_indices_instead_of_reference_row_numbers(tmp_path):
    from participant_bench.hybrid_evaluation import compare_fields, export_analysis

    source = tmp_path / "source"
    write_json(source / "manifest.json", dict(inputs=[dict(sha256="doc")]))
    fields = [
        dict(
            class_id="123456",
            reference_row=reference,
            field="first_name",
            document_id="doc",
            page_number=1,
            output_index=index,
            reference_value=name,
            prediction_value=name,
            exact=True,
        )
        for reference, index, name in [(2, 1, "Anna"), (9, 0, "Ben")]
    ]
    analysis, rows = compare_fields(
        fields, fields, key_fields=("class_id", "reference_row"), normalize=lambda value, field: value or ""
    )
    output = tmp_path / "out"
    export_analysis(output, analysis, rows, source=source)
    exported = csv_rows(output / "hybrid_fields.csv")
    assert [row["reference_row"] for row in exported] == ["9", "2"]
    assert [row["output_index"] for row in exported] == ["0", "1"]
    assert analysis["counts"]["both_correct"] == 2
