"""Response and export contracts; model doubles here make no claims about recognition quality."""

import csv
import json
from pathlib import Path

import pymupdf
import pytest
from participant_bench import runner
from participant_bench.config import load_config
from participant_bench.io import read_jsonl, write_json
from participant_bench.models import LocalModel
from participant_bench.report import report
from participant_bench.schema import PageResult, VisualPageResponse
from PIL import Image
from pydantic import ValidationError


def response_data():
    return {
        "page_text": "Anwesenheit 20.10.2026\nNotiz <script>alert(1)</script>\nAnna Weber 00123 MUC",
        "participants": [{
            "row_ref": "1", "first_name": "Anna", "last_name": "Weber",
            "personnel_number": "00123", "department": "MUC", "signature_present": False,
        }],
    }


def response_model(payload, reached=False):
    model = object.__new__(LocalModel)
    model.method = "vlm"
    model.spec = load_config(Path("configs/local.yaml")).models["vlm"]
    model.calls = 0
    model.generate = lambda *args: (payload, {"output_budget_reached": reached, "output_tokens": 8192 if reached else 200})
    return model


def test_primary_participant_rows_preserve_values_and_suppress_full_text():
    data = response_data()
    data["participants"][0].update(personnel_number=None, department="")
    parsed = VisualPageResponse.model_validate_json(json.dumps(data))
    row = parsed.participants[0].participant()
    assert parsed.page_text is None  # Full text is reserved for the fallback, even if a model supplies both.
    assert row.first_name.value == "Anna" and row.first_name.state == "read"
    assert row.personnel_number.value is None and row.personnel_number.state == "uncertain"
    assert row.department.value == "" and row.department.state == "empty"
    assert row.signature_present is False and row.signature_state == "empty"
    data["participants"][0]["personnel_number"] = 123
    with pytest.raises(ValidationError):
        VisualPageResponse.model_validate_json(json.dumps(data))


def test_vlm_reading_prioritizes_participants_and_keeps_leading_zeroes():
    data = response_data()
    model = response_model(json.dumps(data))
    with Image.new("RGB", (256, 256)) as image:
        participants, responses, status, _ = model.extract(image)
    assert status == "success" and model.calls == 1
    assert participants[0].personnel_number.value == "00123"
    assert responses[0]["page_text"] is None
    assert responses[0]["text_fallback"] is False
    assert responses[0]["raw_response"] == json.dumps(data)  # Diagnostic raw output stays unchanged.


@pytest.mark.parametrize("missing", ["", "   ", "\t\n", None])
def test_missing_user_cell_preserves_person_and_short_code_without_shifting(missing):
    data = response_data()
    data["participants"][0].update(personnel_number=missing, department="FG-123/42")
    model = response_model(json.dumps(data))
    with Image.new("RGB", (256, 256)) as image:
        people, responses, status, _ = model.extract(image)
    assert status == "success" and len(people) == 1
    assert people[0].first_name.value == "Anna" and people[0].department.value == "FG-123/42"
    assert people[0].department.state == "read"
    assert people[0].personnel_number.value == (None if missing is None else "")
    assert people[0].personnel_number.state == ("uncertain" if missing is None else "empty")
    assert not responses[0]["text_fallback"]


def test_empty_short_code_does_not_consume_alphanumeric_user_id():
    data = response_data()
    data["participants"][0].update(personnel_number="u00456", department="")
    row = VisualPageResponse.model_validate_json(json.dumps(data)).participants[0].participant()
    assert row.personnel_number.value == "u00456" and row.personnel_number.state == "read"
    assert row.department.value == "" and row.department.state == "empty"


def test_report_exports_an_empty_user_cell_in_its_own_column(tmp_path):
    data = response_data()
    data["participants"][0].update(personnel_number="", department="FG-123/42")
    row = VisualPageResponse.model_validate_json(json.dumps(data)).participants[0].participant()
    page = PageResult(run_id="fixture", document_id="doc", page_number=1, page_id="doc-p0001",
                      method_id="vlm", status="success", parse_status="valid", participants=[row])
    report(tmp_path, {"vlm": {"status": "success"}}, {"vlm": [page]}, {},
           {"automatic_page_selection": False, "pages": []}, {})
    with (tmp_path / "extractions.csv").open(encoding="utf-8-sig", newline="") as handle:
        exported = list(csv.DictReader(handle))[0]
    assert exported["personnel_number"] == "" and exported["personnel_number_state"] == "empty"
    assert exported["department"] == "FG-123/42" and exported["first_name"] == "Anna"


def test_page_without_people_still_returns_its_entire_text():
    data = {"page_text": "Schulungsunterlagen\nTermin 20.10.2026", "participants": []}
    model = response_model(json.dumps(data))
    with Image.new("RGB", (256, 256)) as image:
        participants, responses, status, _ = model.extract(image)
    assert status == "success" and not participants
    assert responses[0]["page_text"] == data["page_text"]
    assert responses[0]["text_fallback"] is True


def test_empty_participant_result_requires_text_fallback_and_accepts_a_blank_page():
    with pytest.raises(ValidationError, match="provide the visible page text as fallback"):
        VisualPageResponse.model_validate_json('{"participants": [], "page_text": null}')
    blank = VisualPageResponse.model_validate_json('{"participants": [], "page_text": ""}')
    assert blank.page_text == "" and not blank.participants


def test_token_exhaustion_is_explicit_and_retains_unmodified_output():
    raw = '{"page_text": "abgebrochener Text'
    model = response_model(raw, reached=True)
    with Image.new("RGB", (256, 256)) as image:
        participants, responses, status, _ = model.extract(image)
    assert status == "failed" and not participants
    assert model.calls == 1  # No unrecorded repair or inference retry.
    assert responses[0]["error_stage"] == "output_budget"
    assert "max_new_tokens" in responses[0]["error"]
    assert responses[0]["raw_response"] == raw


def test_report_exports_text_and_explains_response_errors_without_page_judgement(tmp_path):
    good = PageResult(
        run_id="fixture", document_id="doc", page_number=1, page_id="doc-p0001", method_id="vlm",
        status="success", parse_status="valid", page_text=response_data()["page_text"],
    )
    bad = PageResult(
        run_id="fixture", document_id="doc", page_number=2, page_id="doc-p0002", method_id="vlm",
        status="failed", parse_status="invalid",
    )
    raw = '{"page_text": "unvollständig <script>"'
    write_json(tmp_path / "vlm/raw-doc-p0002.json", {"responses": [{
        "raw_response": raw, "output_budget_reached": True, "error": "Legacy JSON EOF",
    }]})
    manifest = {"automatic_page_selection": False, "curated": False, "pages": [
        {"page_id": p.page_id, "source_path": "123456.pdf", "page_number": p.page_number,
         "status": "ready", "include": True, "review_required": True}
        for p in (good, bad)
    ]}
    report(tmp_path, {"vlm": {"status": "partial"}}, {"vlm": [good, bad]}, {}, manifest, {})
    assert (tmp_path / "vlm/texts/doc-p0001.txt").read_text(encoding="utf-8") == good.page_text
    assert (tmp_path / "vlm/raw_text/doc-p0002.txt").read_text(encoding="utf-8") == raw
    assert read_jsonl(tmp_path / "page_text.jsonl")[0]["page_text"] == good.page_text
    assert read_jsonl(tmp_path / "page_text.jsonl")[1]["output_budget_reached"] is True
    content = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "am Ausgabelimit abgeschnitten" in content
    assert "keine Bewertung, ob eine PDF-Seite eine Anwesenheitsliste ist" in content
    assert "&lt;script&gt;" in content and "<script>" not in content
    assert "Seitentext als TXT" in content and "Unveränderte Modellantwort" in content


def test_report_prioritizes_participant_fields_and_omits_unnecessary_full_text(tmp_path):
    parsed = VisualPageResponse.model_validate_json(json.dumps(response_data()))
    page = PageResult(
        run_id="fixture", document_id="doc", page_number=1, page_id="doc-p0001", method_id="vlm",
        status="success", parse_status="valid", participants=[p.participant() for p in parsed.participants],
        page_text="Full text from an older run must not be shown when participants were found.",
    )
    manifest = {"automatic_page_selection": False, "pages": [{
        "page_id": page.page_id, "source_path": "123456.pdf", "page_number": 1,
        "status": "ready", "include": True, "review_required": False,
    }]}
    report(tmp_path, {"vlm": {"status": "success"}}, {"vlm": [page]}, {}, manifest, {})
    content = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Anna" in content and "00123" in content
    assert "Full text from an older run" not in content
    assert not (tmp_path / "vlm/texts/doc-p0001.txt").exists()
    exported = read_jsonl(tmp_path / "page_text.jsonl")[0]
    assert exported["page_text"] is None and exported["text_fallback"] is False


def test_runner_propagates_model_output_errors_into_saved_page_results(tmp_path, monkeypatch):
    class FailedResponseModel:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, *args):
            return [], [{"parse_status": "invalid", "error": "Ausgabelimit erreicht",
                         "output_budget_reached": True, "raw_response": '{"page_text": "abgebrochen'}], "failed", 0.0

        def resources(self):
            return {}

        def close(self):
            pass

    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as doc:
        doc.new_page().insert_text((50, 50), "Synthetische Eingabe")
        doc.save(raw / "123456.pdf")
    config = load_config(Path("configs/vlm-smoke.yaml"))
    config.pdf.auto_orient = False
    config.output_dir = str(tmp_path / "runs")
    config.models["vlm"].path = str(tmp_path / "no-model-used-by-this-unit-test")
    monkeypatch.setattr(runner, "LocalModel", FailedResponseModel)
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, _ = runner.run(config, raw)
    result = read_jsonl(output / "vlm/extractions.jsonl")[0]
    assert result["error"] == "Ausgabelimit erreicht" and result["status"] == "failed"
    assert read_jsonl(output / "errors.jsonl")[0]["reason"] == "Ausgabelimit erreicht"
    assert "am Ausgabelimit abgeschnitten" in (output / "report.html").read_text(encoding="utf-8")
