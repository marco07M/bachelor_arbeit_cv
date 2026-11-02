"""Independent synthetic cell evidence and exact expected organization values."""

from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from participant_bench.column_headers import ORGANIZATION_ALIASES, field_roles
from participant_bench.config import load_config
from participant_bench.io import read_json, write_json, write_jsonl
from participant_bench.structure_diagnostics import analyze_page, diagnose_run, reference_ocr_cause
from participant_bench.structure_experiment import variants
from participant_bench.structured_mapping import extract_structured, table_rows
from participant_bench.table_mapping import extract_docling


def native_table(headers, values):
    cells = [dict(text=text, start_row_offset_idx=r, end_row_offset_idx=r+1,
        start_col_offset_idx=c, end_col_offset_idx=c+1, row_span=1, col_span=1,
        column_header=r == 0, bbox=dict(l=c*100, t=r*50, r=c*100+90, b=r*50+40, coord_origin="TOPLEFT"))
        for r, row in enumerate([headers, *values]) for c, text in enumerate(row)]
    html = "<table>"+"".join("<tr>"+"".join(f"<td>{text}</td>" for text in row)+"</tr>" for row in [headers, *values])+"</table>"
    return dict(tables=[dict(html=html, native=dict(data=dict(num_rows=len(values)+1,
        num_cols=len(headers), table_cells=cells)))], plain_text="native OCR retained", markdown=html,
        native=dict(pages={"1": dict(size=dict(width=len(headers)*100, height=800))}))


@pytest.mark.parametrize("alias", ORGANIZATION_ALIASES)
def test_organization_heading_variants(alias):
    source = native_table(["Nachname", alias, "First Name", "User ID"], [["Muster", "ABC-12", "Max", "000007"]])
    people, proofs, _, _ = extract_structured(source)
    assert len(people) == 1 and people[0].department.value == "ABC-12"
    assert people[0].personnel_number.value == "000007"
    assert proofs[0]["fields"]["department"]["heading"][0]["text"] == alias
    assert "department" in field_roles("  "+alias.upper()+"  ")


def test_native_grid_prevents_loss_during_html_export():
    source = native_table(["First Name", "Last Name", "Org.-Einheit"], [["Max", "Muster", "ABC-12"]])
    source["tables"][0]["html"] = "<table><tr><th>First Name</th><th>Last Name</th></tr><tr><td>Max</td><td>Muster</td></tr></table>"
    before, _, _, _ = extract_docling(deepcopy(source))
    after, evidence, _, _ = extract_structured(source)
    assert before[0].department.value is None
    assert after[0].department.value == "ABC-12" and evidence[0]["grid_source"] == "native"
    assert source["tables"][0]["html"].count("<th>") == 2


def test_two_semantically_distinct_organization_columns_are_not_arbitrarily_merged():
    source = native_table(["Vorname", "Nachname", "Organization", "Abteilung"], [["Max", "Muster", "ABC", "XYZ"]])
    people, _, _, _ = extract_structured(source)
    assert len(people) == 1 and people[0].department.value is None
    assert any("column_mapping_failed" in n for n in people[0].review_notes)


def test_unknown_org_heading_keeps_partial_person_and_original_cell():
    source = native_table(["Vorname", "Nachname", "Unbekanntes Feld"], [["Max", "Muster", "ABC-12"]])
    people, proofs, _, _ = extract_structured(source)
    assert len(people) == 1 and people[0].department.value is None
    assert "ABC-12" in proofs[0]["raw_cells"]


def test_explicit_empty_and_missing_native_cell_are_different():
    source = native_table(["Vorname", "Nachname", "Organisation"], [["Max", "Muster", ""], ["Nora", "Fischer", "XYZ"]])
    source["tables"][0]["native"]["data"]["table_cells"].pop()
    people, _, _, _ = extract_structured(source)
    assert people[0].department.state == "empty"
    assert people[1].department.value is None and people[1].department.state != "empty"


def test_repeated_headers_do_not_remove_preceding_participants():
    source = native_table(["Vorname", "Nachname", "Org."], [["Max", "Muster", "ABC"],
        ["Vorname", "Nachname", "Org."], ["Nora", "Fischer", "XYZ"]])
    assert [p.department.value for p in extract_structured(source)[0]] == ["ABC", "XYZ"]


def test_multiline_and_merged_organization_cell_remain_auditable():
    source = native_table(["Vorname", "Nachname", "Organisation"], [["Max", "Muster", "ABC\n12"]])
    assert extract_structured(deepcopy(source))[0][0].department.value == "ABC 12"
    source["tables"][0]["native"]["data"]["table_cells"][-1]["end_col_offset_idx"] = 4
    assert not table_rows(source["tables"][0])[0]  # An invalid grid is not silently replaced by HTML.


def test_missing_text_does_not_invent_ocr_failure_type():
    source = dict(tables=[], native={}, ocr_cells=[])
    assert reference_ocr_cause(source, "ABC-12") == "unknown"
    box = dict(x0=.1,y0=.1,x1=.2,y1=.2)
    source["detection_boxes"] = []
    assert reference_ocr_cause(source, "ABC-12", box) == "ocr_detection_failed"
    source["detection_boxes"] = [box]
    assert reference_ocr_cause(source, "ABC-12", box) == "ocr_recognition_failed"


def test_diagnosis_and_overlay_do_not_modify_existing_output(tmp_path):
    source, output = tmp_path / "run", tmp_path / "diagnosis"
    source.mkdir()
    recognized = native_table(["Vorname", "Nachname", "Organization"], [["Max", "Muster", "ABC"]])
    people, proofs, _, _ = extract_structured(recognized)
    recognized["row_evidence"] = proofs
    raw = dict(page_id="doc-p0001", method_id="docling", structure=recognized)
    write_json(source / "docling/raw-doc-p0001.json", raw)
    write_json(source / "summary.json", dict(docling={}))
    write_jsonl(source / "docling/extractions.jsonl", [dict(page_id="doc-p0001", participants=[p.model_dump() for p in people])])
    image = tmp_path / "page.png"
    Image.new("RGB", (500, 800), "white").save(image)
    write_json(source / "manifest.json", dict(pages=[dict(page_id="doc-p0001", image=str(image))]))
    original = (source / "docling/raw-doc-p0001.json").read_bytes()
    diagnose_run(source, output)
    assert (output / "docling/p00001/overlay.png").is_file()
    assert read_json(output / "diagnosis.json")["quality_measured"] is False
    assert (source / "docling/raw-doc-p0001.json").read_bytes() == original
    with pytest.raises(ValueError):
        diagnose_run(source, output)


def test_llm_omission_is_distinguished_from_position_rejection():
    from test_structure_assignment import paddle

    source = paddle()
    source["row_evidence"] = [dict(output_index=0, source_row="t0r1", fields={})]
    raw = dict(page_id="doc-p0001", method_id="paddle_llm", structure=source,
        assignment=dict(raw_response='{"participants":[{"source_row":"t0r1","department":null}]}',
            text_prompt='{"current_rows":[{"id":"t0r1","cells":[[0,"MUC-1"]]}]}'))
    analysis = analyze_page(raw, dict(participants=[dict(department=None)]))
    assert analysis["traces"][0]["cause"] == "llm_extraction_failed"


def test_controlled_matrix_is_frozen_and_full_page_ocr_is_explicit():
    config = load_config(Path("configs/benchmark.yaml"))
    experiment = variants(config, include_full_page=True)
    assert len(experiment) == 5 and config.methods != ["docling"]
    assert all(v.models == config.models for _, v in experiment)
    assert [v.structures["docling"].force_full_page_ocr for _, v in experiment] == [False]*4+[True]
    assert {v.structures["docling"].table_mode for _, v in experiment} == {"fast", "accurate"}


def test_targeted_org_ambiguity_and_signature_column_are_preserved():
    from test_structure_assignment import paddle

    from participant_bench.structure_assignment import ambiguous_header_fields, header_bands, prepare_rows

    source = paddle()
    source["organization_header_aliases"] = list(ORGANIZATION_ALIASES)
    source["native"]["overall_ocr_res"]["rec_texts"][3] = "Signatur"
    rows, _, _ = prepare_rows(source, "paddle_structure")
    assert header_bands(rows)["department"][1] < .8
    source["native"]["overall_ocr_res"]["rec_texts"][3] = "Organisation"
    rows, _, _ = prepare_rows(source, "paddle_structure")
    assert "department" in ambiguous_header_fields(rows)


def test_intentional_trainer_exclusion_is_not_normalization_failure():
    source = native_table(["Vorname", "Nachname", "Organisation"], [["Max", "Muster", "ABC"]])
    source["row_evidence"] = [dict(output_index=0, source_row="t0r1", fields={})]
    result = analyze_page(dict(method_id="docling", structure=source,
        person_role_filter=dict(excluded=[dict(source_output_index=0)]),
        assignment=dict(participants_after_position_validation=[dict(department=dict(value="ABC"))])),
        dict(participants=[]))
    assert result["traces"] == []


def test_quality_comparison_without_truth_does_not_invent_scores():
    from participant_bench.structure_experiment import quality_summary, render_experiment

    assert quality_summary(None, []) == dict(quality_measured=False)
    # A partial report exists even if inference has not completed a single variant.
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        render_experiment(root, [])
        assert "Zwischenstand" in (root/"report.html").read_text(encoding="utf-8")


def test_full_experiment_uses_all_raw_pages_after_development_guard(tmp_path, monkeypatch):
    import participant_bench.structure_experiment as module

    seen = []
    def stop(config, folder, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("controlled test stop before any model")
    monkeypatch.setattr(module, "run", stop)
    with pytest.raises(RuntimeError, match="controlled test"):
        module.experiment(tmp_path, Path("configs/benchmark.yaml"), tmp_path.parent/(tmp_path.name+"-experiment"))
    assert seen[0]["split"] == "all" and seen[0]["offline"]


def test_active_optimized_profile_retains_explicit_baseline():
    optimized = load_config(Path("configs/benchmark.yaml"))
    baseline = load_config(Path("configs/structures-baseline.yaml"))
    assert optimized.structures["docling"].mapping == "structured"
    assert optimized.structures["docling"].do_cell_matching is False
    assert optimized.structures["docling"].force_full_page_ocr is False
    assert optimized.structures["paddle_llm"].assignment_format == "legacy_v13"
    candidate = load_config(Path("configs/paddle-positioned.yaml"))
    assert candidate.structures["paddle_llm"].assignment_format == "positioned_v14"
    assert "Org.-Einheit" in optimized.structures["docling"].organization_header_aliases
    assert "Org.-Einheit" in candidate.structures["paddle_llm"].organization_header_aliases
    assert baseline.structures["docling"].mapping == "legacy_html"
    assert baseline.structures["docling"].do_cell_matching is True
    assert baseline.structures["paddle_llm"].assignment_format == "legacy_v13"
    assert baseline.models == optimized.models


def test_mapping_and_prompt_options_share_identical_recognition_cache():
    from participant_bench.config import StructureConfig
    from participant_bench.structure import recognition_key

    config = load_config(Path("configs/benchmark.yaml"))
    settings = StructureConfig(models_dir="synthetic", extraction="llm")
    page = dict(document_id="doc", page_number=1, run_image_sha256="same pixels")
    original = recognition_key({"engine":"test"}, settings, config, page, "docling")
    settings.mapping = "structured"
    settings.assignment_format = "positioned_v14"
    settings.organization_header_aliases = ["Org.-Einheit"]
    assert recognition_key({"engine":"test"}, settings, config, page, "docling") == original
    settings.do_cell_matching = False
    assert recognition_key({"engine":"test"}, settings, config, page, "docling") != original
