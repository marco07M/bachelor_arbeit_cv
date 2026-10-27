"""Authored cell-reference tests; model doubles do not measure model quality."""

import json
from pathlib import Path

import pytest
from PIL import Image

from participant_bench.config import Config, ModelConfig, load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_json
from participant_bench.runner import run
from participant_bench.schema import PageResult
from participant_bench.unlimited_assignment import (
    AssignmentResponse,
    assign_pages,
    ground_response,
    source_rows,
    table_headers,
)
from participant_bench.unlimited_reassign import reassign_run

HTML = """<table><tr><td colspan="4">Course metadata</td></tr>
<tr><td rowspan="2">Benutzer</td><td rowspan="2">Name, Vorname (Druckbuchstaben)</td>
<td colspan="2">Other fields</td></tr><tr><td>Kurzzeichen</td><td>Unterschrift</td></tr>
<tr><td></td><td>Groß-Müller, Zoë</td><td>XY/42</td><td></td></tr>
<tr><td>00123</td><td>D'Arcy, Anne Marie</td><td></td><td></td></tr></table>"""


def answer(row="t0r3", **changes):
    values = dict(source_row=row, first_name=[1, "Zoë"], last_name=[1, "Groß-Müller"],
                  personnel_number=[0, ""], department=[2, "XY/42"])
    values.update(changes)
    return values


def grounded(*answers, text=HTML):
    rows, _ = source_rows(text)
    return ground_response(AssignmentResponse.model_validate_json(json.dumps(dict(participants=answers))), rows)


def test_spans_preserve_physical_cells_and_header_columns():
    rows, notes = source_rows(HTML)
    assert not notes and len(rows) == 5
    assert rows[2]["cells"][0]["column_start"] == 2
    headers, mapping = table_headers(rows)
    assert [row["id"] for row in headers] == ["t0r1", "t0r2"]
    assert mapping[0]["personnel_number"] == {0} and mapping[0]["department"] == {2}
    assert rows[3]["cells"][0]["text"] == ""


def test_benutzername_is_combined_name_header_not_user_id():
    rows, _ = source_rows(HTML.replace("Name, Vorname (Druckbuchstaben)", "Benutzername"))
    _, mapping = table_headers(rows)
    assert mapping[0]["first_name"] == mapping[0]["last_name"] == {1}
    assert mapping[0]["personnel_number"] == {0}


def test_generic_name_header_allows_grounded_split_without_overwriting_surname():
    people, _, _ = grounded(answer(), text=HTML.replace("Name, Vorname (Druckbuchstaben)", "Name"))
    assert people[0].first_name.value == "Zoë" and people[0].last_name.value == "Groß-Müller"


def test_markdown_preserves_leading_and_trailing_empty_cells():
    text = "|Benutzer|Benutzername|Kurzzeichen|Unterschrift|\n|---|---|---|---|\n||Groß-Müller, Zoë|XY/42||"
    rows, _ = source_rows(text)
    assert len(rows[1]["cells"]) == 4 and rows[1]["cells"][0]["text"] == ""
    people, _, _ = grounded(answer("t0r1"), text=text)
    assert people[0].personnel_number.state == "empty" and people[0].department.value == "XY/42"


def test_plain_text_header_does_not_assign_whole_row_to_user_id():
    text = "Vorname Nachname Benutzer Kurzzeichen\nZoë Groß-Müller 00123 XY/42"
    people, _, _ = grounded(answer("t0r1", first_name=[0, "Zoë"], last_name=[0, "Groß-Müller"],
                                  personnel_number=[0, "00123"], department=[0, "XY/42"]), text=text)
    assert people[0].personnel_number.value == "00123" and people[0].department.value == "XY/42"


def test_partly_masked_user_id_remains_unknown_with_original_cell_preserved():
    people, proof, _ = grounded(answer("t0r4", first_name=[1, "Anne Marie"], last_name=[1, "D'Arcy"],
        personnel_number=[0, "12***45"], department=[2, ""]), text=HTML.replace("00123", "12***45"))
    assert people[0].personnel_number.value is None and people[0].personnel_number.state == "uncertain"
    assert proof[0]["source_cells"][0]["text"] == "12***45"


def test_literal_combined_names_empty_ids_and_leading_zeroes():
    people, proof, notes = grounded(answer(), answer("t0r4", first_name=[1, "Anne Marie"],
        last_name=[1, "D'Arcy"], personnel_number=[0, "00123"], department=[2, ""]))
    assert len(people) == 2 and not notes
    assert people[0].personnel_number.state == "empty" and people[0].department.value == "XY/42"
    assert people[1].personnel_number.value == "00123" and people[1].first_name.value == "Anne Marie"
    assert proof[0]["source_row"] == "t0r3" and proof[0]["fields"]["first_name"]["offset"]
    assert all(person.signature_present is None and person.bbox is None and person.row_ref is None for person in people)


@pytest.mark.parametrize("change", [dict(first_name=[1, "Zoe"]), dict(first_name=[1, "Groß"]),
                                    dict(first_name=[1, "Anne Marie"])])
def test_invented_cross_row_and_incomplete_word_evidence_is_rejected(change):
    people, _, _ = grounded(answer(**change))
    assert people[0].first_name.state == "failed"
    assert people[0].last_name.value == "Groß-Müller"


def test_wrong_cell_reference_is_recovered_only_from_unique_same_row_evidence():
    people, proof, _ = grounded(answer(first_name=[9, "Zoë"]))
    assert people[0].first_name.value == "Zoë"
    assert proof[0]["fields"]["first_name"]["cell_index"] == 1
    assert any("Zellindex" in note for note in people[0].review_notes)


def test_empty_user_column_cannot_take_department_even_if_model_shifts_it():
    people, _, _ = grounded(answer(personnel_number=[2, "XY/42"]))
    assert people[0].personnel_number.value == "" and people[0].personnel_number.state == "empty"
    assert people[0].department.value == "XY/42"


def test_unknown_duplicate_and_header_source_rows_are_not_people():
    assert not grounded(answer("t99r0"))[0]
    assert not grounded(answer(), answer())[0]
    assert not grounded(answer("t0r1"))[0]


def test_overlapping_name_fragments_are_not_accepted_as_two_fields():
    people, _, _ = grounded(answer(first_name=[1, "Groß-Müller"]))
    assert not people


def test_nested_tables_remain_review_cases():
    rows, notes = source_rows("<table><tr><td><table><tr><td>A</td></tr></table></td></tr></table>")
    assert not rows and notes


def test_cloud_assignment_configuration_rejected_before_document_reading():
    with pytest.raises(ValueError, match="keine API"):
        Config(methods=["unlimited_ocr"], models={
            "unlimited_ocr": ModelConfig(repo="test/ocr", path="x", revision="a" * 40, options={"extraction": "llm"}),
            "ocr_llm": ModelConfig(backend="external", options={"x": 1}),
        })


class AssignmentDouble:
    def __init__(self, config, events):
        self.spec, self.identity = config.models["ocr_llm"], {"synthetic": True}
        self.calls, self.events = 0, events
        events.append("llm_load")

    def generate(self, text, **kwargs):
        assert "column_start" in text and "previous_headers" in text
        self.events.append("llm_assign")
        return json.dumps(dict(participants=[answer()])), {"output_budget_reached": False, "output_tokens": 30}

    def resources(self):
        return dict(load_seconds=0, warmup_seconds=0, warmup_calls=0, calls=self.calls)

    def close(self):
        self.events.append("llm_close")


def pipeline(tmp_path, monkeypatch, fail=False):
    from test_unlimited import SimulatedUnlimited

    events = []
    raw = tmp_path / "input"
    raw.mkdir()
    Image.new("RGB", (600, 800), "white").save(raw / "page.png")
    config = load_config(Path("configs/unlimited-ocr-llm.yaml"))
    config.pdf.include_images, config.pdf.auto_orient = True, False
    config.signature.backend = "opencv"
    config.output_dir, config.cache_dir = str(tmp_path / "runs"), str(tmp_path / "cache")

    class OCRDouble(SimulatedUnlimited):
        def request(self, request):
            response = super().request(request)
            response["raw_response"] = HTML
            return response

        def close(self):
            events.append("ocr_close")

    def factory(method, config, **kwargs):
        if method == "unlimited_ocr":
            return OCRDouble(method, config, kwargs.get("progress"))
        model = AssignmentDouble(config, events)
        if fail:
            model.generate = lambda *a, **k: ("invalid", {"output_budget_reached": fail == "truncated"})
        return model

    monkeypatch.setattr("participant_bench.runner.create_model", factory)
    monkeypatch.setattr("participant_bench.runner.model_identity", lambda spec: {"synthetic": True})
    output, summary = run(config, raw, offline=True)
    return output, config, summary, events


def test_pipeline_unloads_ocr_before_llm_and_exports_evidence(tmp_path, monkeypatch):
    output, _, summary, events = pipeline(tmp_path, monkeypatch)
    assert events.index("ocr_close") < events.index("llm_load") < events.index("llm_assign") < events.index("llm_close")
    pages = read_jsonl(output / "unlimited_ocr/extractions.jsonl")
    assert len(pages[0]["participants"]) == 1 and pages[0]["output_kind"] == "structured"
    assert summary["unlimited_ocr"]["status"] == "partial"
    assert read_json(output / "prompts.json")["assignment_schema"]["title"] == "AssignmentResponse"
    saved = read_json(next((output / "unlimited_ocr").glob("raw-*.json")))
    assert saved["assignment"]["complete"] and saved["unlimited_ocr"]["clean_text"] == HTML
    report = (output / "report.html").read_text(encoding="utf-8")
    assert "LLM-Eingabe zur Zellzuordnung" in report and "lokales LLM" in report


@pytest.mark.parametrize("failure", ["invalid", "truncated"])
def test_failed_assignment_retains_ocr_and_does_not_claim_valid_json(tmp_path, monkeypatch, failure):
    output, _, _, events = pipeline(tmp_path, monkeypatch, fail=failure)
    page = read_jsonl(output / "unlimited_ocr/extractions.jsonl")[0]
    assert page["parse_status"] == "invalid" and not page["participants"]
    assert page["error"] and "Groß-Müller" in page["page_text"]
    assert events[-1] == "llm_close"


def test_reassign_preserves_source_and_reuses_cache(tmp_path, monkeypatch):
    source, config, _, events = pipeline(tmp_path, monkeypatch)
    files = [source / "unlimited_ocr/extractions.jsonl", *list((source / "unlimited_ocr").glob("raw-*.json"))]
    hashes = {path: file_hash(path) for path in files}
    monkeypatch.setattr("participant_bench.unlimited_reassign.create_model", lambda *a, **k: AssignmentDouble(config, events))
    before_calls = events.count("llm_assign")
    output = reassign_run(source, config)
    assert events.count("llm_assign") == before_calls
    assert all(file_hash(path) == sha for path, sha in hashes.items())
    assert read_json(output / "assignment_recheck.json")["new_ocr_inference"] is False
    assert (output / "report.html").is_file()


def test_header_context_is_document_local_and_contains_no_previous_people(tmp_path):
    from participant_bench.progress import Progress

    config = load_config(Path("configs/unlimited-ocr-llm.yaml"))
    config.cache_dir = str(tmp_path / "cache")
    pages = [PageResult(run_id="test", document_id=doc, page_number=number, page_id=f"{doc}{number}",
                        method_id="unlimited_ocr", status="partial")
             for doc, number in [("a", 1), ("a", 2), ("b", 1)]]
    directory = tmp_path / "method"
    for page in pages:
        write_json(directory / f"raw-{page.page_id}.json", {
            "unlimited_ocr": dict(clean_text=HTML, plain_text="synthetic plain text"),
        })
    assign_pages(pages, directory, config, Progress(enabled=False), lambda: AssignmentDouble(config, []))
    records = [read_json(directory / f"raw-{page.page_id}.json")["assignment"] for page in pages]
    prompts = [json.loads(record["text_prompt"]) for record in records]
    assert prompts[0]["previous_headers"] == prompts[2]["previous_headers"] == []
    assert prompts[1]["previous_headers"]
    assert "Zoë" not in json.dumps(prompts[1]["previous_headers"], ensure_ascii=False)
