"""Text-only extraction improvements: physical cells, explicit context exclusion and row-local grounding."""

import json

import pytest
from PIL import Image, ImageDraw
from test_ocr_fixes import model_response, ocr_data, word

from participant_bench.document_names import infer_text_order
from participant_bench.models import LocalModel, generation_schema, parse_ocr_response
from participant_bench.ocr_layout import compact_layout, with_table_columns
from participant_bench.schema import NameOrderDecision, OCRRecordResponse
from participant_bench.structure_assignment import continue_name_column, merge_aligned_fragments
from participant_bench.unlimited_assignment import (
    AssignmentResponse,
    ground_response,
    parse_assignment_response,
    source_rows,
)

HTML = ("<table><tr><td>Name, Vorname</td><td>Benutzer</td><td>Kurzzeichen</td></tr>"
        "<tr><td>von der Wiese, Anna Maria</td><td>000007</td><td>MUC</td></tr>"
        "<tr><td>Muster, Max</td><td>000008</td><td>BER</td></tr></table>")


def row(source="t0r1", **changes):
    result = dict(source_row=source, is_participant=True, first_name="Anna Maria", last_name="von der Wiese",
                  personnel_number="000007", department="MUC")
    return result | changes


def parse(*people):
    rejected = []
    answer = json.dumps(dict(participants=list(people)))
    response = parse_assignment_response(answer, rejected)
    rows, _ = source_rows(HTML)
    return response, rejected, ground_response(response, rows)


def test_value_only_protocol_preserves_names_zeroes_and_cell_evidence():
    _, rejected, (people, proofs, _) = parse(row())
    assert not rejected
    assert people[0].first_name.value == "Anna Maria" and people[0].last_name.value == "von der Wiese"
    assert people[0].personnel_number.value == "000007"
    assert proofs[0]["fields"]["first_name"]["cell_index"] == 0


def test_generation_does_not_ask_small_model_for_cell_indices_or_coordinates():
    schema = generation_schema(AssignmentResponse)
    fields = schema["$defs"]["AssignedRow"]
    assert "is_participant" in fields["required"]
    for field in ("first_name", "last_name", "personnel_number", "department"):
        assert fields["properties"][field]["anyOf"] == [{"type": "string"}, {"type": "null"}]


@pytest.mark.parametrize("change", [dict(personnel_number=7), dict(first_name=[0.25, "Anna Maria"]),
                                    dict(source_row=1), dict(is_participant="false")])
def test_one_malformed_assignment_does_not_discard_other_valid_people(change):
    _, rejected, (people, _, _) = parse(row(), row("t0r2", **change))
    assert len(rejected) == len(people) == 1
    assert rejected[0]["stage"] == "schema"
    assert "input" not in json.dumps(rejected)


def test_legacy_cell_reference_protocol_remains_readable():
    response, rejected, (people, _, _) = parse(dict(source_row="t0r1", first_name=[0, "Anna Maria"],
        last_name=[0, "von der Wiese"], personnel_number=[1, "000007"], department=[2, "MUC"]))
    assert not rejected and len(response.participants) == len(people) == 1


def test_other_rows_are_context_and_cannot_supply_names():
    _, _, (people, _, _) = parse(row(first_name="Max", last_name="Muster"))
    assert people[0].first_name.value is None and people[0].last_name.value is None
    assert people[0].personnel_number.value == "000007"  # Own-row partial evidence survives.
    _, _, (people, _, _) = parse(row(is_participant=False))
    assert not people


def test_invalid_json_is_not_repaired():
    with pytest.raises(ValueError):
        parse_assignment_response('{"participants":[', [])


def test_ocr_context_record_is_explicitly_excluded_without_fabricating_a_person():
    payload = json.loads(model_response())
    payload["participants"][0]["is_participant"] = False
    rejected = []
    assert parse_ocr_response(json.dumps(payload), ocr_data(), rejected, preserve_partial_fields=True) == []
    assert rejected[0]["stage"] == "not_participant"


@pytest.mark.parametrize("line_id", [1, 99])
def test_wrong_ocr_line_reference_can_be_recovered_from_two_unique_own_row_fields(line_id):
    data = ocr_data()
    for item in data["words"]:
        item["line"] = [1, 1, 2]
    data["words"].insert(0, word("Hinweis", 0.1, 0.1))
    payload = json.loads(model_response())
    payload["participants"][0].update(ocr_line_id=line_id, word_ids=[])
    warnings = []
    people = parse_ocr_response(json.dumps(payload), data, [], preserve_partial_fields=True, field_warnings=warnings)
    assert people[0].first_name.value == "Anna" and people[0].last_name.value == "Weber"
    assert any(warning["field"] == "ocr_line_id" for warning in warnings)


def test_recovery_never_combines_names_from_different_people():
    data = ocr_data()
    data["words"] = [word("Hinweis", .1, .1, 1), word("Anna", .1, .3, 2), word("Weber", .3, .5, 3)]
    payload = json.loads(model_response())
    payload["participants"][0].update(ocr_line_id=1, personnel_number=None, department=None, row_ref=None, word_ids=[])
    rejected = []
    assert not parse_ocr_response(json.dumps(payload), data, rejected, preserve_partial_fields=True)


def test_physical_cells_keep_codes_out_of_surname_without_losing_original_words():
    data = ocr_data()
    data["physical_columns"] = [0.0, .45, .65, 1.0]
    payload = json.loads(model_response())
    payload["participants"][0]["last_name"] = "Weber 00123 MUC"
    person = parse_ocr_response(json.dumps(payload), data, [], preserve_partial_fields=True)[0]
    assert person.first_name.value == "Anna" and person.last_name.value is None
    assert person.personnel_number.value == "00123" and person.department.value == "MUC"
    packed = json.loads(compact_layout(data))
    assert packed["lines"][0]["cells"][0]["text"] == "1 Anna Weber"
    assert packed["lines"][0]["cells"][1]["text"] == "00123"
    assert [word[1] for word in packed["words"]] == [word["text"] for word in data["words"]]


def test_table_geometry_enrichment_does_not_change_ocr_text_or_word_ids():
    data = ocr_data()
    before = json.dumps(data)
    with Image.new("RGB", (1000, 1000), "white") as image:
        draw = ImageDraw.Draw(image)
        for x in (50, 450, 650, 950):
            draw.line((x, 100, x, 900), fill="black", width=3)
        enriched = with_table_columns(data, image)
    assert json.dumps(data) == before
    assert enriched["words"] == data["words"] and enriched["text"] == data["text"]
    assert len(enriched["physical_columns"]) >= 5


def text_source():
    rows, _ = source_rows(HTML)
    for source in rows:
        source["column_texts"] = [dict(column=cell["column_start"], text=cell["text"]) for cell in source["cells"]]
    return dict(text_rows=rows, name_column_hint=0)


def test_valid_record_array_and_verified_input_echo_keep_the_names():
    data = text_source()
    source = data["text_rows"][1]
    item = row(cells=source["column_texts"], id=source["id"], column_texts=source["column_texts"])
    warnings = []
    people = parse_ocr_response(json.dumps([item]), data, [], field_warnings=warnings)
    assert len(people) == 1 and people[0].first_name.value == "Anna Maria"
    assert people[0].last_name.value == "von der Wiese" and not warnings


def test_an_unverified_extra_cell_payload_is_rejected_per_row():
    data = text_source()
    rejected = []
    people = parse_ocr_response(json.dumps([row(cells=["Invented"]),
        row("t0r2", first_name="Max", last_name="Muster", personnel_number="000008", department="BER")]),
        data, rejected)
    assert len(people) == len(rejected) == 1
    assert people[0].first_name.value == "Max" and rejected[0]["stage"] == "schema"


@pytest.mark.parametrize("extra", [dict(id="wrong-source"), dict(column_texts=[dict(column=0, text="Invented")])])
def test_wrong_echoed_identity_or_column_text_is_never_ignored(extra):
    rejected = []
    assert parse_ocr_response(json.dumps([row(**extra)]), text_source(), rejected) == []
    assert rejected[0]["stage"] == "schema"


def test_text_name_column_rejects_department_as_a_surname():
    warnings = []
    people = parse_ocr_response(json.dumps([row(last_name="MUC")]), text_source(), [], field_warnings=warnings)
    assert people[0].first_name.value == "Anna Maria" and people[0].last_name.value is None
    assert warnings


def test_bare_numbers_without_any_name_do_not_become_people_in_a_name_table():
    assert parse_ocr_response(json.dumps([row(first_name=None, last_name=None)]), text_source(), []) == []
    people = parse_ocr_response(json.dumps([row(first_name="Anna Maria", last_name=None)]), text_source(), [])
    assert len(people) == 1 and people[0].first_name.value == "Anna Maria"


def test_oversized_name_order_reason_does_not_discard_people():
    rejected = []
    response = parse_assignment_response(json.dumps(dict(
        name_order=dict(order="family_given", evidence="Header evidence " * 100), participants=[row()])), rejected)
    assert len(response.participants) == 1 and not rejected


def test_short_name_order_step_uses_only_the_same_text_model():
    class TextModel:
        calls = 0

        def generate(self, text, image=None, **options):
            assert image is None and options["response_type"] is NameOrderDecision
            assert options["max_new_tokens"] == 192
            assert "von der Wiese" in text and "Benutzer" in text
            return '{"order":"family_given","evidence":"Name, Vorname"}', dict(output_budget_reached=False)

    model = TextModel()
    decision, record = infer_text_order(model, text_source()["text_rows"], 0)
    assert decision.order == "family_given" and record["model_call"] and model.calls == 1
    assert record["parse_status"] == "valid"


def test_text_record_generation_separates_order_and_person_fields():
    from types import SimpleNamespace

    model = object.__new__(LocalModel)
    model.method, model.calls = "ocr_llm", 0
    model.spec = SimpleNamespace(tile_height=None, preserve_partial_fields=True)
    inputs = []
    def generate(text, image=None, **options):
        assert image is None
        inputs.append(options["response_type"])
        if options["response_type"] is NameOrderDecision:
            answer = dict(order="family_given", evidence="Name, Vorname")
        else:
            assert options["response_type"] is OCRRecordResponse
            answer = dict(participants=[row()])
        return json.dumps(answer), dict(output_budget_reached=False)
    model.generate = generate
    data = text_source()
    data["text"] = " ".join(cell["text"] for source in data["text_rows"] for cell in source["cells"])
    data["words"] = []
    with Image.new("RGB", (100, 100)) as image:
        people, records, _, _ = model.extract(image, data)
    assert len(people) == 1 and records[0]["name_order"]["order"] == "family_given"
    assert inputs == [NameOrderDecision, OCRRecordResponse] and model.calls == 2


def test_continuation_column_context_never_reuses_person_text_or_crosses_changed_layout():
    native = [dict(text="Weber Anna", bbox=dict(x0=.21, y0=.4, x1=.38, y1=.42)),
              dict(text="ABC-12", bbox=dict(x0=.5, y0=.4, x1=.6, y1=.42))]
    rows = [dict(id="t0r0", native_cells=native)]
    context = dict(aspect=.7, boundaries=[0, .1, .2, .4, .7, 1], hint=2, bounds=[.2, .4])
    result, hint, bounds = continue_name_column(rows, [0, .1, .4, 1], .7, context)
    assert hint == 2 and bounds == [.2, .4]
    assert result[0]["column_texts"] == [dict(column=2, text="Weber Anna"), dict(column=3, text="ABC-12")]
    assert "Weber" not in json.dumps(context)
    for changed, aspect in (([0, .5, .8, 1], .7), ([0, .1, .4, 1], 1.4)):
        unchanged, hint, bounds = continue_name_column(rows, changed, aspect, context)
        assert unchanged == rows and hint is None and bounds is None


def test_flat_name_box_remains_in_its_own_physical_person_row():
    def fragment(text, x0, x1, y0, y1):
        return ((y0+y1)/2, dict(text=text, bbox=dict(x0=x0, x1=x1, y0=y0, y1=y1)))
    flat = fragment("Anna", .25, .30, .559, .561)
    tall = fragment("Weber", .20, .24, .555, .582)
    next_person = fragment("Muster", .20, .24, .579, .597)
    groups = [[flat], [tall], [next_person]]
    combined = merge_aligned_fragments(groups, [0, .1, .4, 1], .016)
    assert combined == [[flat, tall], [next_person]]
    assert merge_aligned_fragments(groups, [], .016) == groups


def test_close_neighbouring_people_are_never_joined_at_the_same_column_position():
    boxes = [(y + .01, dict(text="Weber Anna", bbox=dict(x0=.2, x1=.4, y0=y, y1=y+.02)))
             for y in [.40, .41]]
    groups = [[box] for box in boxes]
    assert merge_aligned_fragments(groups, [0, .1, .5, 1], .02) == groups
