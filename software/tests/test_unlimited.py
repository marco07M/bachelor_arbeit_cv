"""Native adapter contracts with authored OCR output; doubles do not measure model accuracy."""

from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from participant_bench.config import load_config
from participant_bench.io import file_hash, read_json, read_jsonl, write_csv
from participant_bench.ocr_evaluation import evaluate_text
from participant_bench.runner import run
from participant_bench.unlimited import UnlimitedModel, UnlimitedOptions, runtime_paths
from participant_bench.unlimited_tables import clean_text, extract_tables, plain_text

TABLE = """<table><tr><th>Vorname</th><th>Nachname</th><th>Benutzer</th><th>Kurzzeichen</th><th>Unterschrift</th></tr>
<tr><td>Zoë</td><td>Groß-Müller</td><td></td><td>XY/42</td><td></td></tr>
<tr><td>Anne Marie</td><td>D'Arcy</td><td>00123</td><td></td><td>mark</td></tr></table>"""


@pytest.fixture(autouse=True)
def isolate_checkpoint_metadata(monkeypatch):
    monkeypatch.setattr("participant_bench.runner.model_identity", lambda spec: {"synthetic": spec.repo})


def test_cells_preserve_names_empty_ids_leading_zeroes_and_signatures():
    people, evidence, notes = extract_tables(TABLE)
    assert len(people) == 2 and not notes
    assert people[0].first_name.value == "Zoë" and people[0].last_name.value == "Groß-Müller"
    assert people[0].personnel_number.value == "" and people[0].personnel_number.state == "empty"
    assert people[0].department.value == "XY/42"
    assert people[1].personnel_number.value == "00123" and people[1].department.state == "empty"
    assert people[1].first_name.value == "Anne Marie" and people[1].last_name.value == "D'Arcy"
    assert all(person.signature_present is None and person.bbox is None for person in people)
    assert evidence[0]["source_row_index"] == 1 and evidence[0]["raw_cells"][2] == ""


def test_markdown_reordered_columns_and_unknown_fields_are_not_guessed():
    text = "| User ID | Last Name | First Name |\n|---|---|---|\n|00042|Müller|Ana|\n| |Weber| |"
    people, evidence, notes = extract_tables(text)
    assert len(people) == 2 and not notes
    assert people[0].personnel_number.value == "00042"
    assert people[0].department.state == "uncertain"
    assert people[1].first_name.state == "empty"
    assert evidence[0]["column_mapping"]["last_name"] == 1


def test_ambiguous_merged_and_broken_tables_require_review():
    merged = TABLE.replace("<td>Zoë", '<td colspan="2">Zoë')
    assert not extract_tables(merged)[0]
    broken = TABLE.replace("<td></td><td>XY/42</td>", "<td>XY/42</td>")
    people, _, notes = extract_tables(broken)
    assert len(people) == 1 and any("Zellzahl" in note for note in notes)
    assert not extract_tables("Vorname und Nachname sind irgendwo im Text")[0]


def test_cleanup_preserves_original_spelling_and_layout_is_separate():
    raw = "<|det|>table [0, 0, 999, 999]<|/det|>" + TABLE + "<｜end▁of▁sentence｜>"
    clean = clean_text(raw)
    assert "<table>" in clean and "00123" in clean and "Zoë" in clean
    assert "<|det|>" not in clean
    assert "<table>" not in plain_text(clean) and "Groß-Müller" in plain_text(clean)


def test_runtime_defaults_do_not_enable_remote_code_or_cpu():
    options = UnlimitedOptions()
    assert options.extraction == "none" and options.precision == "auto"
    _, worker, lock = runtime_paths(options)
    source = worker.read_text(encoding="utf-8")
    assert "trust_remote_code=False" in source and "local_files_only=True" in source
    assert lock.is_file()


class SimulatedUnlimited(UnlimitedModel):
    created = 0

    def __init__(self, method, config, progress=None):
        type(self).created += 1
        self.spec = config.models[method]
        self.options = UnlimitedOptions.model_validate(self.spec.options)
        self.progress = progress
        self.calls = 0
        self._resources = dict(load_seconds=0, warmup_seconds=0, warmup_calls=0)

    def request(self, request):
        return dict(
            raw_response=TABLE,
            clean_text=TABLE,
            detections=[],
            output_budget_reached=False,
            output_tokens=12,
            timings=dict(model_inference_seconds=0.001),
            resources=self._resources,
        )

    def resources(self):
        return dict(self._resources, calls=self.calls)

    def close(self):
        pass


@pytest.mark.parametrize("extraction", ["none", "table"])
def test_pdf_images_report_resume_and_text_evaluation(tmp_path, monkeypatch, extraction):
    from participant_bench import runner

    config = load_config(Path("configs/unlimited-ocr.yaml"))
    config.models["unlimited_ocr"].options["extraction"] = extraction
    config.pdf.auto_orient = False
    config.output_dir = str(tmp_path / "runs")
    config.cache_dir = str(tmp_path / "cache")
    inputs = tmp_path / "input"
    inputs.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((40, 40), "Authored synthetic page one")
        document.new_page().insert_text((40, 40), "Authored synthetic page two")
        document.save(inputs / "123456.pdf")
    with Image.new("RGB", (200, 150), "white") as image:
        image.save(inputs / "sample.PNG")
        image.save(inputs / "sample.jpg")
    originals = {p.name: file_hash(p) for p in inputs.iterdir()}
    monkeypatch.setattr(
        runner,
        "create_model",
        lambda method, config, **kwargs: SimulatedUnlimited(method, config, kwargs["progress"]),
    )
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    SimulatedUnlimited.created = 0
    output, summary = run(config, inputs, offline=True)
    pages = read_jsonl(output / "unlimited_ocr/extractions.jsonl")
    assert len(pages) == 4 and SimulatedUnlimited.created == 1
    assert summary["unlimited_ocr"]["output_kind"] == ("ocr_text" if extraction == "none" else "structured")
    assert all(len(page["participants"]) == (0 if extraction == "none" else 2) for page in pages)
    raw = read_json(next((output / "unlimited_ocr").glob("raw-*.json")))
    assert raw["responses"][0]["raw_response"] == TABLE
    report = (output / "report.html").read_text(encoding="utf-8")
    assert "Unlimited-OCR" in report and "Groß-Müller" in report
    assert (output / "unlimited_ocr/ocr_text").is_dir()
    _, resumed = run(config, inputs, offline=True, resume=output)
    assert resumed["unlimited_ocr"]["resume_reused_pages"] == 4 and SimulatedUnlimited.created == 1
    assert all(file_hash(inputs / name) == value for name, value in originals.items())
    references = tmp_path / "reference"
    references.mkdir()
    (references / "page.txt").write_text(plain_text(TABLE), encoding="utf-8")
    write_csv(
        references / "pages.csv",
        [
            dict(
                document_id=pages[0]["document_id"],
                page_number=pages[0]["page_number"],
                text_reviewed="true",
                reference_text_file="page.txt",
            )
        ],
    )
    evaluation = read_json(evaluate_text(output, references) / "metrics.json")
    assert evaluation["normalized"]["cer"]["value"] == 0
    assert evaluation["unreferenced_prediction_pages"] == 3


def test_one_page_failure_does_not_abort_following_pages(tmp_path, monkeypatch):
    from participant_bench import runner

    config = load_config(Path("configs/unlimited-ocr.yaml"))
    config.pdf.auto_orient = False
    config.output_dir = str(tmp_path / "runs")
    source = tmp_path / "input"
    source.mkdir()
    with pymupdf.open() as document:
        document.new_page()
        document.new_page()
        document.save(source / "123456.pdf")

    class FailingOnce(SimulatedUnlimited):
        def request(self, request):
            if not hasattr(self, "seen"):
                self.seen = True
                raise RuntimeError("Synthetic page failure")
            return super().request(request)

    monkeypatch.setattr(
        runner,
        "create_model",
        lambda method, config, **kwargs: FailingOnce(method, config, kwargs["progress"]),
    )
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    output, _ = run(config, source, offline=True)
    pages = read_jsonl(output / "unlimited_ocr/extractions.jsonl")
    assert [p["status"] for p in pages] == ["failed", "success"]


def test_native_ocr_is_not_scored_as_missing_structured_people(tmp_path, monkeypatch):
    from participant_bench import runner

    config = load_config(Path("configs/unlimited-ocr.yaml"))
    config.pdf.auto_orient = False
    config.output_dir = str(tmp_path / "runs")
    source = tmp_path / "input"
    source.mkdir()
    with pymupdf.open() as document:
        document.new_page()
        document.save(source / "123456.pdf")

    def forbidden(*args, **kwargs):
        pytest.fail("Raw OCR must not receive structured-field scores")

    monkeypatch.setattr(
        runner,
        "create_model",
        lambda method, config, **kwargs: SimulatedUnlimited(method, config, kwargs["progress"]),
    )
    monkeypatch.setattr(runner, "environment", lambda *args: {})
    monkeypatch.setattr(runner, "load_truth", lambda *args: [object()])
    monkeypatch.setattr(runner, "evaluate_groups", forbidden)
    output, _ = run(config, source, offline=True)
    assert (output / "report.html").exists()


def test_raw_field_metric_exposes_name_case_changes():
    from participant_bench.evaluation import evaluate
    from participant_bench.schema import GroundTruthPage, PageResult

    people, _, _ = extract_tables(TABLE)
    truth = GroundTruthPage(
        document_id="synthetic",
        page_number=1,
        split="development",
        dependency_group="synthetic",
        content_type="typed",
        relevant=True,
        participants=people,
    )
    predicted = people[0].model_copy(deep=True)
    predicted.first_name.value = "zoë"
    page = PageResult(
        run_id="test",
        document_id="synthetic",
        page_number=1,
        page_id="p1",
        method_id="unlimited_ocr",
        status="success",
        participants=[predicted, people[1]],
    )
    metrics, _ = evaluate([page], [truth])
    assert metrics["fields"]["first_name"]["exact_match"]["value"] == 1
    assert metrics["fields"]["first_name"]["raw_exact_match"]["value"] == 0.5
    page.output_kind = "ocr_text"
    with pytest.raises(ValueError, match="CER/WER"):
        evaluate([page], [truth])
