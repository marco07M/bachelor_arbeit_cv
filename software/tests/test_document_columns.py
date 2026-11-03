"""Synthetic continuation layouts; these are mapping tests, not handwriting OCR claims."""

import json
from copy import deepcopy

import pytest
from PIL import Image

from participant_bench.column_context import VERSION, compatible, geometry
from participant_bench.models import parse_ocr_response
from participant_bench.ocr_layout import model_input, with_table_columns
from participant_bench.structure_assignment import document_bands, header_bands, prepare_rows
from participant_bench.structured_mapping import extract_structured
from participant_bench.table_mapping import extract_docling

HEADINGS = ["Vorname", "Nachname", "Benutzer", "Organisation"]
VALUES = [["Anna", "Muster", "001234", "ABC-12"]]


def table(headers=HEADINGS, values=None, *, edges=None, header=True):
    values = deepcopy(VALUES if values is None else values)
    rows = [headers, *values] if header else values
    edges = edges or [i / len(headers) for i in range(len(headers)+1)]
    native = [dict(text=text, start_row_offset_idx=r, end_row_offset_idx=r+1,
        start_col_offset_idx=c, end_col_offset_idx=c+1, column_header=header and r == 0,
        bbox=dict(l=edges[c]*1000, r=edges[c+1]*1000-5, t=100+r*60, b=140+r*60))
        for r, row in enumerate(rows) for c, text in enumerate(row)]
    html = "<table>" + "".join("<tr>"+"".join(f"<td>{v}</td>" for v in row)+"</tr>" for row in rows)+"</table>"
    return dict(native=dict(pages={"1": dict(size=dict(width=1000, height=1000))}),
        tables=[dict(html=html, native=dict(data=dict(num_cols=len(headers), num_rows=len(rows), table_cells=native)))],
        plain_text="Synthetic OCR", markdown=html)


def extract(source, context=None, number=1, document="synthetic", mapper=extract_structured):
    return mapper(source, context, document_id=document, page_number=number)


@pytest.mark.parametrize("mapper", [extract_structured, extract_docling])
def test_current_headers_and_headerless_continuation_keep_current_values(mapper):
    people, _, _, context = extract(table(), mapper=mapper)
    assert people[0].personnel_number.value == "001234"
    assert context["version"] == VERSION and context["source_page"] == 1
    assert context["document_id"] == "synthetic" and context["geometry"]["width"] == 4
    assert "001234" not in json.dumps(context) and "Anna" not in json.dumps(context)
    following = table(values=[["Nora", "Beispiel", "009876", "DEF-34"]], header=False)
    after, proofs, _, _ = extract(following, context, 2, mapper=mapper)
    assert [getattr(after[0], field).value for field in ("first_name", "last_name", "personnel_number", "department")] == [
        "Nora", "Beispiel", "009876", "DEF-34"]
    assert proofs[0]["mapping_provenance"]["status"] == "inherited_from_previous_page"
    assert proofs[0]["mapping_provenance"]["source_page"] == 1


def test_cover_before_first_list_and_blank_between_lists_do_not_erase_context():
    empty = dict(tables=[], native={})
    assert extract(empty)[3] == {}
    _, _, _, context = extract(table(), number=2)
    _, _, _, preserved = extract(empty, context, 3)
    assert preserved == context
    people, proof, _, _ = extract(table(header=False), preserved, 4)
    assert len(people) == 1 and proof[0]["mapping_provenance"]["source_page"] == 2


def test_small_width_changes_are_compatible_but_large_column_shifts_are_not():
    _, _, _, context = extract(table())
    people, _, _, _ = extract(table(header=False, edges=[0, .26, .49, .76, 1]), context, 2)
    assert people[0].department.value == "ABC-12"
    source = table(header=False, edges=[0, .38, .6, .8, 1])
    assert not extract(source, context, 2)[0]
    assert source["mapping_diagnostics"][0]["status"] == "incompatible_table_structure"


def test_new_headers_change_order_and_define_the_next_continuation():
    _, _, _, context = extract(table())
    headers = ["Organisation", "Benutzer", "Nachname", "Vorname"]
    values = [["DEF-34", "009876", "Beispiel", "Nora"]]
    current = table(headers, values)
    people, _, _, updated = extract(current, context, 2)
    assert people[0].first_name.value == "Nora" and people[0].department.value == "DEF-34"
    assert current["mapping_diagnostics"][0]["status"] == "updated_on_current_page"
    after, proofs, _, _ = extract(table(headers, values, header=False), updated, 3)
    assert after[0].personnel_number.value == "009876" and proofs[0]["mapping_provenance"]["source_page"] == 2


@pytest.mark.parametrize("case", ["extra_column", "missing_geometry", "merged_grid", "other_document", "earlier_page", "old_version"])
def test_unsafe_inheritance_is_rejected_without_shifting_fields(case):
    _, _, _, context = extract(table())
    source, number, document = table(header=False), 2, "synthetic"
    if case == "extra_column":
        source = table([*HEADINGS, "Zusatz"], [[*VALUES[0], "X"]], header=False)
    elif case == "missing_geometry":
        for c in source["tables"][0]["native"]["data"]["table_cells"]:
            c.pop("bbox")
    elif case == "merged_grid":
        cells = source["tables"][0]["native"]["data"]["table_cells"]
        cells[0]["end_col_offset_idx"] = 2
        cells.pop(1)
    elif case == "other_document":
        document = "different-pdf"
    elif case == "earlier_page":
        number = 1
    else:
        context.pop("version")
    assert not extract(source, context, number, document)[0]


def test_separate_document_states_and_repeated_runs_are_deterministic():
    _, _, _, a = extract(table(), document="A")
    _, _, _, b = extract(table(list(reversed(HEADINGS)), [list(reversed(VALUES[0]))]), document="B")
    first = extract(table(header=False), a, 2, "A")
    second = extract(table(header=False), deepcopy(a), 2, "A")
    assert [p.model_dump() for p in first[0]] == [p.model_dump() for p in second[0]]
    assert first[3] == second[3] == a
    assert a["mapping"] != b["mapping"] and not extract(table(header=False))[0]


def test_partial_handwritten_observations_and_empty_neighbors_keep_their_columns():
    _, _, _, context = extract(table())
    people, proofs, _, _ = extract(table(values=[["An…", "Muster", "", "ABC-12"]], header=False), context, 2)
    assert people[0].first_name.value == "An…" and people[0].first_name.state == "uncertain"
    assert people[0].personnel_number.state == "empty" and people[0].department.value == "ABC-12"
    assert proofs[0]["fields"]["department"]["native_ref"].endswith("/3")


def test_controlled_two_page_recall_gain_is_current_evidence_not_copied_values():
    from participant_bench.schema import TEXT_FIELDS

    first, _, _, context = extract(table())
    values = [["Nora", "Beispiel", "009876", "DEF-34"]]
    before = extract(table(values=values, header=False), number=2)[0]
    after = extract(table(values=values, header=False), context, 2)[0]
    assert not before and len(after) == 1
    expected = [*VALUES[0], *values[0]]
    observed = [getattr(p, f).value for p in [*first, *after] for f in TEXT_FIELDS]
    assert observed == expected  # 4/8 -> 8/8 exact fields; no additional wrong values.


def test_resume_restore_checks_scope_and_clears_explicitly_invalidated_context():
    from participant_bench.structure import StructureModel

    _, _, _, context = extract(table())
    model = object.__new__(StructureModel)
    model.mapping_context = {}
    page = dict(document_id="synthetic", page_number=1)
    model.restore_mapping(page, dict(structure=dict(table_mapping_context=context)))
    assert model.mapping_context["synthetic"] == context
    model.restore_mapping(dict(document_id="foreign", page_number=2), dict(structure=dict(table_mapping_context=context)))
    assert "foreign" not in model.mapping_context
    model.restore_mapping(page, dict(structure=dict(table_mapping_context={})))
    assert not model.mapping_context


def test_ambiguous_new_headings_cannot_reactivate_stale_headers():
    _, _, _, context = extract(table())
    source = table(["Vorname", "Nachname", "Organisation", "Abteilung"])
    _, _, _, updated = extract(source, context, 2)
    assert not updated
    assert not extract(table(header=False), updated, 3)[0]


def words(headers=True):
    values = [HEADINGS, VALUES[0]] if headers else VALUES
    return dict(text="Synthetic unchanged OCR", words=[dict(text=text, bbox=dict(
        x0=c*.25+.02, x1=c*.25+.15, y0=.1+r*.1, y1=.12+r*.1), line=[1, 1, r+1], ocr_confidence=90)
        for r, row in enumerate(values) for c, text in enumerate(row)])


def test_tesseract_passes_all_inherited_field_columns_and_rejects_wrong_id(monkeypatch):
    monkeypatch.setattr("participant_bench.column_context.image_boundaries", lambda image: [0., .25, .5, .75, 1.])
    with Image.new("RGB", (50, 50), "white") as image:
        first = with_table_columns(words(), image, document_id="A", page_number=1)
        data = words(False)
        enriched = with_table_columns(data, image, first, document_id="A", page_number=2)
        other = with_table_columns(data, image, first, document_id="B", page_number=2)
    assert enriched["words"] == data["words"] and enriched["text"] == data["text"]
    assert enriched["column_mapping"] == {"first_name": [0], "last_name": [1], "personnel_number": [2], "department": [3]}
    assert not other["column_mapping"] and enriched["name_column_hint"] is None
    assert "inherited_from_previous_page" in model_input(enriched)
    payload = dict(participants=[dict(source_row="r1", first_name="Anna", last_name="Muster",
        personnel_number="ABC-12", department="ABC-12")])
    people = parse_ocr_response(json.dumps(payload), enriched, [])
    assert people[0].personnel_number.value is None and people[0].department.value == "ABC-12"


def test_paddle_inherits_only_when_current_measured_grid_matches():
    from test_structure_assignment import paddle

    first, second = paddle(), paddle(headings=False)
    for item in (first, second):
        item["image_column_boundaries"] = [0., .2, .55, .75, 1.]
    rows, _, _ = prepare_rows(first, "paddle_structure")
    bands = header_bands(rows)
    _, context, trace = document_bands(first, rows, bands, None, document_id="A", page_number=1)
    assert trace["status"] == "detected_on_current_page"
    rows, _, _ = prepare_rows(second, "paddle_structure")
    inherited, _, trace = document_bands(second, rows, {}, context, document_id="A", page_number=2)
    assert inherited and trace["source_page"] == 1
    second["image_column_boundaries"] = [0., .15, .4, .55, .75, 1.]
    inherited, _, trace = document_bands(second, rows, {}, context, document_id="A", page_number=2)
    assert not inherited and trace["status"] == "incompatible_table_structure"
    assert not compatible(geometry(4, boundaries=[0., .2, .55, .75, 1.]), None)[0]
