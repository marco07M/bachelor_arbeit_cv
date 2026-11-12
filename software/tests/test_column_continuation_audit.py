"""Current-page evidence and explicit audit of multi-page column continuation."""

import csv
import json
from copy import deepcopy

import pytest
from PIL import Image, ImageDraw
from test_document_columns import HEADINGS, VALUES, table, words
from test_field_pipeline_trace import visual

from participant_bench.column_context import geometry, image_boundaries, resolve
from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.ocr_layout import with_table_columns
from participant_bench.report import report
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.error_report import render_errors
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.roster_benchmark.pipeline_trace import field_trace, page_trace
from participant_bench.schema import Box, NameOrderDecision, PageResult
from participant_bench.structure_assignment import document_bands, header_bands, prepare_rows
from participant_bench.structured_mapping import extract_structured
from participant_bench.table_mapping import extract_docling


def orphan_observations():
    return [dict(index=c, text=value, bbox=dict(x0=c*.25+.02, x1=c*.25+.15, y0=.2, y1=.24))
            for c, value in enumerate(["Nora", "Beispiel", "009876", "DEF-34"])]


@pytest.mark.parametrize("case", ["missing_geometry", "fewer_columns", "no_table"])
def test_unverified_previous_intervals_cannot_bypass_rejected_continuation(case):
    _, _, _, context = extract_structured(table(), document_id="doc", page_number=1)
    current = table(header=False)
    if case == "missing_geometry":
        for cell in current["tables"][0]["native"]["data"]["table_cells"]:
            cell.pop("bbox")
    elif case == "fewer_columns":
        current = table(HEADINGS[:3], [VALUES[0][:3]], header=False, edges=[0, .3, .6, 1])
    else:
        current["tables"] = []
    current["ocr_cells"] = orphan_observations()
    people, proofs, _, _ = extract_structured(current, context, document_id="doc", page_number=2)
    assert not people and not proofs
    assert not any(t.get("inherited_column_intervals") for t in current["mapping_diagnostics"])


def test_tesseract_multiline_headings_keep_all_four_roles_on_later_pages(monkeypatch):
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0, .25, .5, .75, 1])
    data = words()
    first = deepcopy(data["words"][:2])
    second = deepcopy(data["words"][2:4])
    for word in second:
        word.update(line=[1, 1, 2], bbox=dict(word["bbox"], y0=.13, y1=.15))
    for word in data["words"][4:]:
        word["line"] = [1, 1, 3]
    data["words"] = first + second + data["words"][4:]
    with Image.new("RGB", (100, 100), "white") as image:
        initial = with_table_columns(data, image, document_id="doc", page_number=1)
        following = with_table_columns(words(False), image, initial, document_id="doc", page_number=2)
    expected = dict(first_name=[0], last_name=[1], personnel_number=[2], department=[3])
    assert initial["column_mapping"] == following["column_mapping"] == expected
    assert following["mapping_provenance"]["source_page"] == 1


def test_visual_inherited_separate_name_columns_use_only_current_cells():
    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, first = visual(HEADINGS, VALUES[0], profile=profile)
    people, _, warnings, audit = visual(
        [None]*4, ["Nora", "Beispiel", "009876", "DEF-34"], first["column_context"], 2, profile=profile)
    assert [getattr(people[0], key).value for key in ("first_name", "last_name", "personnel_number", "department")] == [
        "Nora", "Beispiel", "009876", "DEF-34"]
    assert not warnings
    assert "Nora" not in json.dumps(audit["column_context"])


def test_inheritance_audit_identifies_fields_headings_and_geometry_check():
    _, _, _, context = extract_structured(table(), document_id="doc", page_number=1)
    current = table(header=False, edges=[0, .26, .49, .76, 1])
    _, proofs, _, _ = extract_structured(current, context, document_id="doc", page_number=2)
    trace = proofs[0]["mapping_provenance"]
    assert trace["column_mapping"] == dict(first_name=[0], last_name=[1], personnel_number=[2], department=[3])
    assert trace["headings"] == context["headings"]
    check = trace["geometry_check"]
    assert check["compatible"] is True and check["max_edge_shift"] == pytest.approx(.01)
    assert check["allowed_edge_shift"] == .035
    assert "Anna" not in json.dumps(trace) and "001234" not in json.dumps(trace)


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_visual_continuation_does_not_fill_current_empty_names_from_semantic_values(empty):
    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, initial = visual(HEADINGS, VALUES[0], profile=profile)
    people, _, _, audit = visual([None]*4, [empty, "Beispiel", "009876", ""], initial["column_context"], 2, profile=profile)
    assert people[0].first_name.value == (None if empty is None else "")
    assert people[0].department.value == ""
    assert audit["mapping_provenance"]["column_mapping"]["first_name"] == [0]


def test_spatial_multiline_headers_use_physical_columns_and_project_all_target_bands():
    # An unmapped leading column must not shift the four target roles to indices 0..3.
    edges = [0, .1, .325, .55, .775, 1]
    observed = [(title, [edges[c+1]*1000+10, y, edges[c+1]*1000+90, y+18])
                for c, title in enumerate(HEADINGS) for y in [100 if c < 2 else 150]]
    recognized = dict(tables=[], image_column_boundaries=edges,
        native=dict(width=1000, height=1000, overall_ocr_res=dict(
            rec_texts=[t for t, _ in observed], rec_boxes=[b for _, b in observed])))
    rows, _, _ = prepare_rows(recognized, "paddle_structure")
    bands = header_bands(rows)
    assert set(bands) == {"first_name", "last_name", "personnel_number", "department"}
    _, context, _ = document_bands(recognized, rows, bands, None, document_id="doc", page_number=1)
    assert context["mapping"] == dict(first_name=[1], last_name=[2], personnel_number=[3], department=[4])
    assert context["text_width"] == 5
    following = dict(image_column_boundaries=[0, .1, .33, .56, .78, 1])
    inherited, _, trace = document_bands(following, [], {}, context, document_id="doc", page_number=2)
    assert set(inherited) == set(bands) and trace["status"] == "inherited_from_previous_page"
    assert trace["observed_cell_bands"]["personnel_number"] == [.56, .78]


def test_real_grid_detector_accepts_three_physical_columns_for_combined_names():
    with Image.new("RGB", (600, 400), "white") as image:
        draw = ImageDraw.Draw(image)
        for x in (0, 200, 400, 599):
            draw.line((x, 40, x, 350), fill="black", width=3)
        for y in (40, 120, 200, 280, 350):
            draw.line((0, y, 599, y), fill="black", width=3)
        assert image_boundaries(image) == pytest.approx([0, 1/3, 2/3, 1], abs=.01)


def test_context_discards_data_appended_to_heading_cells_and_other_row_properties():
    mapping = dict(first_name={0}, last_name={1}, personnel_number={2}, department={3})
    headings = {field: [dict(text=title + "\nPRIVATE_VALUE_123", column=i,
                             participant="PRIVATE_VALUE_456")]
                for i, (field, title) in enumerate(zip(mapping, HEADINGS, strict=True))}
    _, context, trace = resolve(mapping, headings, geometry(4, boundaries=[0, .25, .5, .75, 1]),
        document_id="doc", page_number=1, has_header=True)
    assert context["headings"]["personnel_number"][0]["text"] == "Benutzer"
    assert "PRIVATE_VALUE" not in json.dumps(context) + json.dumps(trace)
    assert "PRIVATE_VALUE" in json.dumps(headings)  # Caller data is unchanged.


@pytest.mark.parametrize("changed", ["new_headers", "ambiguous_headers", "other_pdf", "changed_geometry"])
def test_visual_new_headings_override_and_unsafe_continuations_never_reuse_roles(changed):
    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, initial = visual(HEADINGS, VALUES[0], profile=profile)
    titles, cells, document = [None]*4, ["Nora", "Beispiel", "009876", "DEF-34"], "doc"
    if changed == "new_headers":
        titles, cells = list(reversed(HEADINGS)), list(reversed(cells))
    elif changed == "ambiguous_headers":
        titles = ["Vorname", "Nachname", "Organisation", "Abteilung"]
    elif changed == "other_pdf":
        document = "other"
    else:
        profile = geometry(4, boundaries=[0, .35, .6, .85, 1])
    people, _, _, audit = visual(titles, cells, initial["column_context"], 2, document, profile)
    if changed == "new_headers":
        assert people[0].personnel_number.value == "009876" and people[0].first_name.value == "Nora"
        assert audit["column_context"]["source_page"] == 2
        assert audit["mapping_provenance"]["status"] == "updated_on_current_page"
    else:
        assert people[0].personnel_number.value is None
        assert audit["mapping_provenance"]["status"] != "inherited_from_previous_page"
        if changed == "ambiguous_headers":
            assert not audit["column_context"]


@pytest.mark.parametrize("method", ["ocr_llm", "paddle_llm", "vlm", "ocr_vlm", "docling"])
def test_run_report_and_page_chain_include_saved_field_mapping_and_reason(tmp_path, method):
    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, initial = visual(HEADINGS, VALUES[0], profile=profile)
    people, _, _, audit = visual([None]*4, ["Nora", "Beispiel", "009876", "DEF-34"], initial["column_context"], 2, profile=profile)
    trace = audit["mapping_provenance"]
    raw = (dict(responses=[dict(identity_column_assignment=audit)]) if method in ("vlm", "ocr_vlm") else
           dict(ocr_layout_analysis=dict(mapping_provenance=trace)) if method == "ocr_llm" else
           dict(assignment=dict(document_column_mapping=trace)) if method == "paddle_llm" else
           dict(structure=dict(mapping_diagnostics=[trace], markdown="", clean_text="", plain_text="", tables=[])))
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0002", page_number=2,
                      method_id=method, status="success", parse_status="valid", participants=people)
    write_json(tmp_path / method / "raw-doc-p0002.json", raw)
    report(tmp_path, {method: dict(status="success")}, {method: [page]}, {}, dict(pages=[]), {})
    with (tmp_path / "document_column_mappings.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["source_page"] == "1"
    assert "personnel_number" in rows[0]["column_mapping"] and "department" in rows[0]["column_mapping"]
    assert "passende gemessene X-Positionen" in rows[0]["explanation"]
    assert "allowed_edge_shift" in rows[0]["geometry_check"]
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Feld → Spaltenindex" in html and "Vergleich mit Quellseite" in html
    assert page_trace(tmp_path, page, raw, {}, [])["column_mappings"] == [trace]


@pytest.mark.parametrize("mapper", [extract_structured, extract_docling])
def test_explicit_partial_new_headers_block_the_previous_full_layout(mapper):
    _, _, _, context = mapper(table(), document_id="doc", page_number=1)
    current = table(["", "", "Organisation", "Personalnummer"], [["Nora", "Beispiel", "DEF-34", "009876"]])
    people, _, _, updated = mapper(current, context, document_id="doc", page_number=2)
    assert not updated
    assert people[0].department.value == "DEF-34" and people[0].personnel_number.value == "009876"
    assert people[0].first_name.value is None and people[0].last_name.value is None
    assert current["mapping_diagnostics"][0]["reason"] == "ambiguous_current_headings"


def test_tesseract_partial_new_headings_do_not_silently_reuse_old_roles(monkeypatch):
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0, .25, .5, .75, 1])
    current = words()
    current["words"] = [w for w in current["words"] if w["text"] not in HEADINGS[:2]]
    current["words"][0]["text"], current["words"][1]["text"] = "Organisation", "Personalnummer"
    with Image.new("RGB", (100, 100), "white") as image:
        initial = with_table_columns(words(), image, document_id="doc", page_number=1)
        following = with_table_columns(current, image, initial, document_id="doc", page_number=2)
    assert following["column_mapping"] == dict(department=[2], personnel_number=[3])
    assert not following["column_mapping_context"]


def test_analysis_html_explains_inheritance_without_changing_saved_grades(tmp_path):
    source, output, reference = tmp_path / "source", tmp_path / "analysis", tmp_path / "reference.csv"
    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, initial = visual(HEADINGS, VALUES[0], profile=profile)
    people, _, _, audit = visual([None]*4, ["Nora", "Beispiel", "009876", "DEF-34"], initial["column_context"], 2, profile=profile)
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0002", page_number=2,
                      method_id="ocr_vlm", status="success", parse_status="valid", participants=people)
    write_json(source / "manifest.json", dict(inputs=[dict(kind="pdf", sha256="doc", path="123456.pdf")]))
    write_json(source / "summary.json", dict(ocr_vlm=dict(status="success", output_kind="structured")))
    write_jsonl(source / "ocr_vlm/extractions.jsonl", [page.model_dump()])
    write_json(source / "ocr_vlm/raw-doc-p0002.json", dict(responses=[dict(identity_column_assignment=audit)]))
    with reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerow(["123456", "009876", "Nora", "Beispiel", "DEF-34"])
    output, _ = evaluate_run(source, reference, BenchmarkConfig(), output)
    saved = {path: file_hash(output / path) for path in ("fields.csv", "metrics.json")}
    render_errors(output)
    assert all(file_hash(output / path) == digest for path, digest in saved.items())
    html = (output / "extraction_errors.html").read_text(encoding="utf-8")
    assert "Feld → Spaltenindex" in html and "Gemessener Geometrievergleich" in html
    assert "passende gemessene X-Positionen" in html and "inherited_from_previous_page" in html
    pipeline = read_json(output / "error_analysis/page_pipeline.json")
    assert pipeline[0]["column_mappings"][0]["column_mapping"]["personnel_number"] == [2]


def test_actual_spatial_llm_input_carries_no_data_appended_to_old_header_cells(tmp_path):
    from test_structure_assignment import LLM, config, paddle, page

    from participant_bench.progress import Progress
    from participant_bench.unlimited_assignment import assign_pages

    settings, pages, prompts = config(tmp_path), [page(1), page(2)], []
    for item in pages:
        recognized = paddle(headings=item.page_number == 1)
        recognized["image_column_boundaries"] = [0, .2, .55, .75, 1]
        if item.page_number == 1:
            recognized["native"]["overall_ocr_res"]["rec_texts"][0] += "\nPRIVATE_PREVIOUS_123"
        write_json(tmp_path / f"raw-{item.page_id}.json", dict(structure=recognized))
    model = LLM(settings.models["ocr_llm"], prompts)
    assign_pages(pages, tmp_path, settings, Progress(enabled=False), lambda: model, method="paddle_structure")
    assert prompts[1]["previous_headers"]
    assert "PRIVATE_PREVIOUS_123" in json.dumps(prompts[0]["current_rows"])
    assert "PRIVATE_PREVIOUS_123" not in json.dumps(prompts[1])


@pytest.mark.parametrize("method", ["ocr_llm", "paddle_llm", "vlm", "ocr_vlm"])
def test_final_name_postprocessing_respects_verified_separate_continuation_columns(method):
    from participant_bench.document_names import DocumentNameOrders

    profile = geometry(4, boundaries=[0, .25, .5, .75, 1])
    _, _, _, initial = visual(HEADINGS, VALUES[0], profile=profile)
    people, _, _, audit = visual([None]*4, ["Nora", "Beispiel", "009876", "DEF-34"], initial["column_context"], 2, profile=profile)
    trace = audit["mapping_provenance"]
    raw = (dict(responses=[dict(identity_column_assignment=audit)]) if method in ("vlm", "ocr_vlm") else
           dict(ocr_layout_analysis=dict(column_mapping=trace["column_mapping"], mapping_provenance=trace)) if method == "ocr_llm" else
           dict(assignment=dict(document_column_mapping=trace)))
    if method in ("vlm", "ocr_vlm"):
        raw["responses"][0]["parse_status"] = "valid"
        raw["responses"][0]["raw_response"] = json.dumps(dict(identity_headers=[None]*4,
            participants=[dict(first_name="Nora", last_name="Beispiel", identity_cells=["Nora", "Beispiel", "009876", "DEF-34"])]))
    else:
        people[0].first_name.bbox = Box(x0=.02, x1=.15, y0=.2, y1=.24)
        people[0].last_name.bbox = Box(x0=.27, x1=.4, y0=.2, y1=.24)
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0002", page_number=2,
                      method_id=method, status="success", parse_status="valid", participants=people)
    DocumentNameOrders().apply(page, raw, NameOrderDecision(order="unknown", basis="unknown", evidence=""))
    assert page.participants[0].first_name.value == "Nora" and page.participants[0].last_name.value == "Beispiel"
    assert page.participants[0].first_name.state == page.participants[0].last_name.state == "read"
    assert raw["document_name_order"]["actions"][0]["assignment_rule"] == "verified_separate_name_columns"
    if method in ("vlm", "ocr_vlm"):
        for field, value in (("first_name", "Nora"), ("last_name", "Beispiel")):
            stages = field_trace(dict(output_index=0), page, raw, {}, [], field)["stages"]
            assert next(s for s in stages if s["stage"] == "model_response")["value"] == value
