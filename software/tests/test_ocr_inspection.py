"""Inspect saved OCR independently of extraction success; retain only observed fields."""

import json

import pytest

from participant_bench.io import digest, file_hash, read_jsonl, write_json, write_jsonl
from participant_bench.models import check_ocr_evidence, parse_ocr_response
from participant_bench.ocr_layout import model_input
from participant_bench.report import refresh_report
from participant_bench.schema import PageResult


def evidence():
    words = [
        {"text": text, "bbox": {"x0": x, "y0": y, "x1": x + 0.05, "y1": y + 0.015},
         "ocr_confidence": 90.0, "line": [1, 1, index // 4 + 1]}
        for index, (text, x, y) in enumerate([
            ("Anna", 0.1, 0.3), ("Weber", 0.3, 0.3), ("00123", 0.5, 0.3), ("MUC", 0.7, 0.3),
            ("Nora", 0.1, 0.5), ("Fischer", 0.3, 0.5), ("00456", 0.5, 0.5), ("BER", 0.7, 0.5),
        ])
    ]
    return {"words": words, "text": " ".join(w["text"] for w in words)}


def prediction(**updates):
    row = {"first_name": "Anna", "last_name": "Weber", "personnel_number": "00123", "department": "MUC",
           "word_ids": [0, 1, 2, 3]}
    row.update(updates)
    return json.dumps({"participants": [row]})


def test_unknown_field_does_not_discard_observed_identity_fields():
    warnings, rejected = [], []
    rows = parse_ocr_response(prediction(first_name="NichtGelesen"), evidence(), rejected,
                              preserve_partial_fields=True, field_warnings=warnings)
    assert not rejected and len(rows) == 1
    assert rows[0].first_name.value is None and rows[0].first_name.state == "failed"
    assert rows[0].personnel_number.value == "00123"
    assert rows[0].last_name.value == "Weber" and rows[0].department.value == "MUC"
    assert warnings[0]["field"] == "first_name" and rows[0].review_notes


def test_person_name_from_another_row_is_never_attached_to_this_personnel_number():
    rows = parse_ocr_response(prediction(first_name="Nora", word_ids=[4, 5, 6, 7]), evidence(), [],
                              preserve_partial_fields=True)
    assert len(rows) == 1 and rows[0].personnel_number.value == "00123"
    assert rows[0].first_name.value is None  # Globally observed is insufficient: wrong physical row.
    assert rows[0].bbox.y1 < 0.4
    assert any("Modellreferenzen" in note for note in rows[0].review_notes)


def test_substring_is_not_an_observed_surname_and_low_confidence_is_exposed():
    data = evidence()
    data["words"][0]["ocr_confidence"] = 10
    rows = parse_ocr_response(prediction(last_name="Web"), data, [], preserve_partial_fields=True)
    assert rows[0].last_name.value is None and rows[0].last_name.state == "failed"
    assert rows[0].first_name.value == "Anna" and rows[0].first_name.state == "uncertain"


def test_wholly_unobserved_row_is_still_rejected():
    rejected = []
    rows = parse_ocr_response(prediction(first_name="Erfunden", last_name="NichtVorhanden",
                                        personnel_number="99999", department="XXX"), evidence(), rejected,
                              preserve_partial_fields=True)
    assert rows == [] and len(rejected) == 1


def test_partial_extraction_keeps_original_observed_spelling():
    rows = parse_ocr_response(prediction(first_name="ANNA"), evidence(), [], preserve_partial_fields=True)
    assert rows[0].first_name.value == "Anna"


def test_outer_punctuation_does_not_discard_observed_surname_or_short_code():
    data = evidence()
    data["words"][1]["text"] = "Weber,"
    data["words"][3]["text"] = "(MUC)"
    rows = parse_ocr_response(prediction(), data, [], preserve_partial_fields=True)
    assert rows[0].last_name.value == "Weber," and rows[0].last_name.state == "read"
    assert rows[0].department.value == "(MUC)" and rows[0].department.state == "read"
    assert not any("failed" == getattr(rows[0], name).state for name in (
        "first_name", "last_name", "personnel_number", "department"))


def test_explicit_ocr_line_keeps_fields_even_when_glyph_boxes_do_not_overlap():
    data = evidence()
    data["words"][0]["bbox"].update(y0=0.28, y1=0.295)
    rows = parse_ocr_response(prediction(), data, [], preserve_partial_fields=True)
    assert rows[0].first_name.value == "Anna" and rows[0].review_notes == []


def test_distinct_ocr_lines_do_not_merge_even_when_glyph_boxes_overlap():
    data = evidence()
    data["words"][4]["bbox"].update(y0=0.29, y1=0.52)
    rows = parse_ocr_response(prediction(first_name="Nora"), data, [], preserve_partial_fields=True)
    assert rows[0].first_name.value is None
    assert "Wortbeleg gehört zu einer anderen OCR-Zeile" in rows[0].review_notes[0]


def test_geometric_evidence_still_connects_separate_ocr_blocks_in_one_table_row():
    data = evidence()
    for index in range(4):
        data["words"][index]["line"] = [index + 1, 1, 1]
    rows = parse_ocr_response(prediction(), data, [], preserve_partial_fields=True)
    assert rows[0].first_name.value == "Anna" and rows[0].department.value == "MUC"
    assert rows[0].review_notes == []


def test_extra_references_to_words_on_same_line_are_valid():
    data = evidence()
    data["words"].append({**data["words"][3], "text": "Zusatz"})
    rows = parse_ocr_response(prediction(word_ids=[0, 1, 2, 3, 8]), data, [], preserve_partial_fields=True)
    assert rows[0].review_notes == []


def test_printed_row_reference_keeps_observed_punctuation_for_subsequent_validation():
    data = evidence()
    data["words"].append({**data["words"][0], "text": "1."})
    data["text"] = " ".join(word["text"] for word in data["words"])
    rows = parse_ocr_response(prediction(row_ref="1", word_ids=[0, 1, 2, 3, 8]),
                              data, [], preserve_partial_fields=True)
    assert rows[0].row_ref == "1."
    check_ocr_evidence(rows, data)


def test_line_reference_disambiguates_repeated_names_without_using_other_persons_id():
    data = evidence()
    data["words"][4]["text"], data["words"][5]["text"] = "Anna", "Weber"
    rows = parse_ocr_response(prediction(ocr_line_id=2, department="BER", word_ids=[4, 5, 6, 7]),
                              data, [], preserve_partial_fields=True)
    assert rows[0].first_name.value == "Anna" and rows[0].last_name.value == "Weber"
    assert rows[0].personnel_number.value is None and rows[0].department.value == "BER"
    assert rows[0].bbox.y0 == 0.5


def test_unknown_ocr_line_reference_is_rejected():
    rejected = []
    assert parse_ocr_response(prediction(ocr_line_id=3), evidence(), rejected,
                              preserve_partial_fields=True) == []
    assert "unbekannte OCR-Zeilenkennung" in rejected[0]["error"]


@pytest.mark.parametrize("matching_prompt", [True, False])
def test_saved_report_shows_ocr_text_even_with_participants_and_refresh_keeps_predictions(tmp_path, matching_prompt):
    data = evidence()
    data["words"].append({"text": "<script>alert(1)</script>", "bbox": {
        "x0": 0.1, "y0": 0.7, "x1": 0.2, "y1": 0.715}, "ocr_confidence": 90, "line": [1, 1, 3]})
    data["text"] += " <script>alert(1)</script>"
    participants = parse_ocr_response(prediction(), data, [], preserve_partial_fields=True)
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0001", page_number=1,
                      method_id="ocr_llm", status="success", parse_status="valid", participants=participants)
    write_json(tmp_path / "summary.json", {"ocr_llm": {"status": "success"}})
    write_json(tmp_path / "metrics.json", {})
    write_json(tmp_path / "costs.json", {})
    write_json(tmp_path / "manifest.json", {"automatic_page_selection": False, "pages": [{
        "page_id": page.page_id, "source_path": "123456.pdf", "page_number": 1,
        "status": "ready", "include": True, "review_required": False,
    }]})
    result_path = tmp_path / "ocr_llm/extractions.jsonl"
    write_jsonl(result_path, [page.model_dump()])
    write_json(tmp_path / "ocr_llm/raw-doc-p0001.json", {"ocr": data, "responses": [{
        "text_prompt_sha256": digest(model_input(data)) if matching_prompt else "different",
    }]})
    hashes = {path: file_hash(path) for path in (result_path, tmp_path / "summary.json", tmp_path / "manifest.json")}
    report_path = refresh_report(tmp_path)
    assert all(file_hash(path) == old for path, old in hashes.items())
    plain_path = tmp_path / "ocr_llm/ocr_text/doc-p0001.txt"
    assert plain_path.is_file() and "Anna Weber 00123 MUC" in plain_path.read_text(encoding="utf-8")
    assert read_jsonl(tmp_path / "page_text.jsonl")[0]["page_text"] is None  # Diagnostic text is separate from fallback.
    assert read_jsonl(tmp_path / "ocr_text.jsonl")[0]["word_count"] == 9
    content = report_path.read_text(encoding="utf-8")
    assert "OCR-Klartext und Modelleingabe" in content and "&lt;script&gt;" in content
    assert "<script>" not in content
    prompts = list((tmp_path / "ocr_llm/model_input").glob("*.txt"))
    assert bool(prompts) == matching_prompt
    if matching_prompt:
        assert prompts[0].read_bytes() == model_input(data).encode("utf-8")
