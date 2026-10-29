"""The new six-method protocol, deterministic Docling and a controlled visual experiment."""

import json
from pathlib import Path

import pytest
from PIL import Image

from participant_bench.config import METHODS, TEXT_MODEL, TEXT_REVISION, Config, load_config
from participant_bench.evaluation import normalized
from participant_bench.hybrid import prepare_hints, serialize_hints
from participant_bench.hybrid_evaluation import compare_fields, export_analysis
from participant_bench.io import write_json
from participant_bench.models import LocalModel, Unavailable
from participant_bench.progress import Progress
from participant_bench.schema import VisualCellPageResponse
from participant_bench.table_mapping import extract_docling


def recognized(html):
    return dict(tables=[dict(html=html)], native={}, plain_text="original OCR", markdown=html)


TABLE = ("<table><tr><th>Organization</th><th>Benutzername</th><th>User ID</th></tr>"
         "<tr><td>ABC-12</td><td>von der Wiese, Anna Maria</td><td>000007</td></tr></table>")


@pytest.mark.parametrize("method", METHODS)
def test_every_main_method_can_be_selected_separately(method):
    data = load_config(Path("configs/benchmark.yaml")).model_dump()
    config = Config.model_validate(dict(data, methods=[method]))
    assert config.methods == [method]
    assert config.models["ocr_llm"].repo == TEXT_MODEL
    assert config.models["ocr_llm"].revision == TEXT_REVISION
    if method == "ocr_vlm":
        assert config.models["ocr_vlm"] == config.models["vlm"]
    if method == "docling":
        assert config.structures["docling"].extraction == "table"


def test_main_protocol_rejects_other_models_and_unfair_visual_parameters():
    data = load_config(Path("configs/benchmark.yaml")).model_dump()
    assert {spec["repo"] for spec in data["models"].values()} == {TEXT_MODEL, "Qwen/Qwen3-VL-4B-Instruct"}
    data["models"]["ocr_llm"]["repo"] = "Qwen/Qwen3-8B"
    with pytest.raises(ValueError, match="Hauptvergleich"):
        Config.model_validate(data)
    data = load_config(Path("configs/benchmark.yaml")).model_dump()
    data["models"]["ocr_vlm"]["max_pixels"] //= 2
    with pytest.raises(ValueError, match="identische"):
        Config.model_validate(data)


def test_older_four_b_weights_are_never_relabelled_as_instruct_2507():
    config = load_config(Path("configs/benchmark.yaml"))
    assert config.models["ocr_llm"].path != "models/qwen3-4b"
    config.models["ocr_llm"].path = "not-installed-synthetic-fixture"
    with pytest.raises(Unavailable, match="Missing weights"):
        LocalModel("ocr_llm", config)


def test_docling_uses_printed_headings_and_explicit_comma_without_any_llm():
    people, evidence, _, context = extract_docling(recognized(TABLE))
    assert len(people) == 1
    person = people[0]
    assert (person.first_name.value, person.last_name.value) == ("Anna Maria", "von der Wiese")
    assert person.personnel_number.value == "000007" and person.department.value == "ABC-12"
    assert person.signature_present is None and person.row_ref is None
    assert evidence[0]["fields"]["first_name"]["assignment_rule"] == "explicit_surname_comma_given_name"
    assert "Anna" not in json.dumps(context)


def test_docling_separate_name_columns_multiline_cells_and_header_spans():
    html = ("<table><tr><th colspan='4'>Teilnehmer</th></tr><tr><th>User ID</th><th>Last Name</th>"
            "<th>Organization</th><th>First Name</th></tr><tr><td>000007</td><td>von der Wiese</td>"
            "<td>ABC-12</td><td>Anna<br>Maria</td></tr></table>")
    people, _, _, _ = extract_docling(recognized(html))
    assert len(people) == 1 and people[0].first_name.value == "Anna Maria"
    assert people[0].last_name.value == "von der Wiese"


def test_docling_never_guesses_a_combined_name_split():
    people, _, notes, _ = extract_docling(recognized(TABLE.replace("von der Wiese, Anna Maria", "unreadable combined text")))
    assert len(people) == 1 and people[0].first_name.value is None and people[0].last_name.value is None
    assert people[0].personnel_number.value == "000007"
    assert any("Komma" in text for text in people[0].review_notes)
    people, _, notes, _ = extract_docling(recognized("<table><tr><td>Unclear</td><td>structure</td></tr></table>"))
    assert not people and notes


def test_docling_does_not_shift_missing_cells_into_other_fields():
    html = "<table><tr><th>User ID</th><th>Benutzername</th><th>Organization</th></tr><tr><td>Muster, Max</td><td>ABC</td></tr></table>"
    people, _, notes, _ = extract_docling(recognized(html))
    assert not people and any("Spaltenverschiebung" in note for note in notes)


def test_docling_continuation_reuses_only_compatible_logical_columns():
    _, _, _, context = extract_docling(recognized(TABLE))
    next_table = "<table><tr><td>XYZ</td><td>Muster, Max</td><td></td></tr></table>"
    people, _, _, _ = extract_docling(recognized(next_table), context)
    assert people[0].first_name.value == "Max" and people[0].personnel_number.state == "empty"
    people, _, _, _ = extract_docling(recognized(next_table.replace("<td>XYZ</td>", "")), context)
    assert not people


def visual_response():
    return json.dumps(dict(name_order=dict(order="family_given", evidence="Name, Vorname"),
        identity_headers=["Name, Vorname", "Benutzer", "Kurzzeichen"], participants=[dict(
            row_ref=None, first_name="Max", last_name="Muster", identity_cells=["Muster, Max", "000007", "ABC"], signature_present=None)], page_text=None))


def test_vlm_and_hybrid_receive_identical_images_schema_and_base_prompt():
    calls = []
    config = load_config(Path("configs/benchmark.yaml"))
    for method in ("vlm", "ocr_vlm"):
        model = object.__new__(LocalModel)
        model.method, model.spec, model.calls = method, config.models[method], 0
        def generate(text, image=None, **options):
            calls.append(dict(text=text, image=image.tobytes(), options=options))
            return visual_response(), dict(output_budget_reached=False)
        model.generate = generate
        with Image.new("RGB", (200, 200), "white") as image:
            people, records, _, _ = model.extract(image, {"hints": {"text": "WrongOCR"}} if method == "ocr_vlm" else None)
        assert len(people) == 1 and records[0]["parse_status"] == "valid"
    assert calls[0]["image"] == calls[1]["image"]
    assert calls[1]["text"].startswith(calls[0]["text"])
    assert "WrongOCR" not in calls[0]["text"] and "WrongOCR" in calls[1]["text"]
    assert calls[0]["options"] == calls[1]["options"]
    assert VisualCellPageResponse.model_validate_json(visual_response())


def test_hybrid_keeps_native_boxes_confidence_and_columns():
    from test_structure_assignment import paddle

    value = paddle()
    value["native"]["overall_ocr_res"]["rec_scores"] = [.9] * len(value["native"]["overall_ocr_res"]["rec_texts"])
    hints = serialize_hints(value)
    assert hints["rows"] and len(hints["rows"][0]["cells"][0]) == 6
    assert hints["rows"][0]["cells"][0][-1] == .9
    assert hints["coordinate_scale"] == 1000
    assert "tables" not in hints  # Native full output remains in the run; prompt carries compact evidence.


def test_hybrid_reuses_paddle_output_without_loading_another_worker(tmp_path):
    from test_structure_assignment import paddle

    page = dict(page_id="doc-p0001", include=True, status="ready", run_image_sha256="image")
    result = paddle()
    result["recognition_seconds"] = 4.5
    write_json(tmp_path / "paddle_llm/raw-doc-p0001.json", dict(run_image_sha256="image", structure=result))
    def forbidden():
        raise AssertionError("Paddle must not be loaded or recognized twice")
    hints, _ = prepare_hints(None, [page], tmp_path, Progress(enabled=False), forbidden)
    assert hints[page["page_id"]]["cache_hit"] and hints[page["page_id"]]["charged_seconds"] == 4.5


def test_missing_paddle_does_not_silently_become_image_only_vlm(tmp_path):
    page = dict(page_id="doc-p0001", include=True, status="ready", run_image_sha256="image")
    calls = []
    def absent():
        calls.append(1)
        raise Unavailable("Not installed")
    records, _ = prepare_hints(None, [page, dict(page, page_id="doc-p0002")], tmp_path, Progress(enabled=False), absent)
    assert len(calls) == 1 and all("error" in record and "hints" not in record for record in records.values())


def test_standalone_hybrid_reads_warm_native_cache_without_loading_gpu_worker(tmp_path, monkeypatch):
    from test_structure_assignment import paddle

    import participant_bench.structure as structure

    cached = dict(paddle(), recognition_seconds=3.25, cache_hit=True)
    monkeypatch.setattr(structure, "recognition_cache_reader", lambda method, config: lambda page: cached)
    page = dict(page_id="doc-p0001", include=True, status="ready", run_image_sha256="image")
    def forbidden():
        raise AssertionError("Warm native cache must not start a GPU worker")
    hints, resources = prepare_hints(object(), [page], tmp_path, Progress(enabled=False), forbidden)
    assert hints[page["page_id"]]["cache_hit"]
    assert hints[page["page_id"]]["charged_seconds"] == 3.25
    assert hints[page["page_id"]]["reused_from_method"] is None
    assert not resources.get("calls")


def test_paired_analysis_counts_repairs_regressions_ids_and_missing_records(tmp_path):
    def field(index, expected, actual, exact):
        return dict(document_id="doc", page_number=1, truth_index=index, field="personnel_number",
                    truth_raw=expected, prediction_raw=actual, exact=exact)
    baseline = [field(0,"000007","000008",False), field(1,"000009","000009",True)]
    hybrid = [field(0,"000007","000007",True), field(1,"000009","000010",False)]
    result, rows = compare_fields(baseline, hybrid, key_fields=("document_id","page_number","truth_index"), normalize=normalized)
    assert result["counts"]["corrected"] == result["counts"]["regressed"] == 1
    assert result["baseline_record_accuracy"] == result["hybrid_record_accuracy"] == .5
    assert result["per_field"]["personnel_number"]["corrected"] == 1
    assert result["per_field"]["personnel_number"]["regressed"] == 1
    assert rows[0]["transition"] == "corrected" and rows[1]["transition"] == "regressed"
    export_analysis(tmp_path, result, rows)
    assert (tmp_path / "hybrid_fields.csv").is_file() and (tmp_path / "hybrid_analysis.html").is_file()
    empty, _ = compare_fields([], [], key_fields=("document_id","page_number","truth_index"), normalize=normalized)
    assert empty["status"] == "not_measured" and empty["hybrid_field_exact"] is None


def test_paired_analysis_rejects_different_ground_truth():
    a = dict(class_id="123456", reference_row=2, field="last_name", reference_value="Muster", exact=True)
    with pytest.raises(ValueError, match="dieselbe Referenz"):
        compare_fields([a], [dict(a, reference_value="Different")], key_fields=("class_id","reference_row"), normalize=normalized)


def test_synthetic_smoke_fixture_has_independent_truth_and_reference(tmp_path):
    import importlib.util

    from participant_bench.io import read_jsonl
    from participant_bench.schema import GroundTruthPage

    spec = importlib.util.spec_from_file_location("benchmark_smoke", "scripts/make_benchmark_smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = module.generate(tmp_path / "fixture")
    truth = GroundTruthPage.model_validate(read_jsonl(root / "ground_truth.jsonl")[0])
    assert len(truth.participants) == 2 and truth.participants[0].personnel_number.value == "000007"
    assert all(person.signature_present is False for person in truth.participants)
    assert (root / "reference.csv").is_file()
    with pytest.raises(FileExistsError):
        module.generate(root)


def test_frozen_pairing_checks_actual_images_and_model_settings(tmp_path):
    import yaml

    from participant_bench.hybrid_evaluation import comparison_controls

    config = load_config(Path("configs/benchmark.yaml"))
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    for method in ("vlm", "ocr_vlm"):
        write_json(tmp_path / method / "raw-doc-p0001.json", dict(page_id="doc-p0001", run_image_sha256="same",
            responses=[dict(prompt_version="same-base-prompt")]))
    assert comparison_controls(tmp_path)["verified"]
    write_json(tmp_path / "ocr_vlm/raw-doc-p0001.json", dict(page_id="doc-p0001", run_image_sha256="different",
        responses=[dict(prompt_version="same-base-prompt")]))
    assert not comparison_controls(tmp_path)["verified"]


def test_bf16_uses_fp16_when_the_detected_gpu_does_not_support_it():
    from test_gpu_loading import spec, torch_double

    from participant_bench.models import model_load_kwargs

    torch = torch_double()
    torch.float16 = "supported-half-precision"
    torch.cuda.is_bf16_supported = lambda: False
    result = model_load_kwargs(spec(device="cuda"), torch, "vlm")
    assert result["dtype"] == "supported-half-precision" and "quantization_config" not in result


@pytest.mark.parametrize("masked,query_length", [(False, 7), (True, 7), (False, 1), (True, 1)])
def test_repeated_kv_attention_preserves_values_and_causal_mask(masked, query_length):
    from types import SimpleNamespace

    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from transformers.integrations.sdpa_attention import sdpa_attention_forward
    from transformers.masking_utils import ALL_MASK_ATTENTION_FUNCTIONS

    from participant_bench.attention import register_repeated_kv_sdpa, repeated_kv_sdpa

    torch.manual_seed(42)
    module = SimpleNamespace(num_key_value_groups=2, is_causal=True)
    query = torch.randn(1, 4, query_length, 8)
    key, value = torch.randn(1, 2, 7, 8), torch.randn(1, 2, 7, 8)
    mask = torch.zeros(1, 1, query_length, 7) if masked else None
    if mask is not None:
        mask[..., -1] = float("-inf")
    expected, _ = sdpa_attention_forward(module, query, key, value, mask, scaling=.3)
    actual, _ = repeated_kv_sdpa(module, query, key, value, mask, scaling=.3)
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
    register_repeated_kv_sdpa()
    assert ALL_MASK_ATTENTION_FUNCTIONS["sdpa_repeated_kv"] is ALL_MASK_ATTENTION_FUNCTIONS["sdpa"]
