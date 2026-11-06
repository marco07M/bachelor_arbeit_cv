"""Observed scalar cells can complete an existing person, never create an identity."""

from copy import deepcopy

import pytest

from participant_bench.schema import TEXT_FIELDS, Participant, TextField
from participant_bench.structure_assignment import complete_observed_cells, document_bands, header_bands


def cell(text, left, right, fields=(), score=.01):
    return dict(text=text, bbox=dict(x0=left, x1=right, y0=.2, y1=.22),
                header_fields=list(fields), ocr_confidence=score, native_ref="synthetic/1", kind="native")


def mapping():
    cells = [cell("Benutzername", .21, .35, ("first_name", "last_name")),
             cell("Kurzzeichen", .41, .49, ("department",)), cell("Signatur", .61, .69, ("signature",))]
    rows = [dict(id="head", cells=cells, native_cells=cells)]
    recognized = dict(image_column_boundaries=[0, .2, .4, .6, .8, 1])
    _, context, trace = document_bands(recognized, rows, header_bands(rows), None, document_id="a", page_number=1)
    return recognized, context, trace


def complete(trace, cells, *, existing=None):
    fields = {f: TextField() for f in TEXT_FIELDS}
    fields.update(last_name=TextField(value="Berg", state="read"), department=existing or TextField())
    person = Participant(**fields)
    proof = dict(source_row="r1", fields={})
    changes = complete_observed_cells([person], [proof], [dict(id="r1", native_cells=cells)], trace)
    return person, proof, changes


def test_unique_cell_with_low_score_is_retained_and_signature_stays_separate():
    _, _, trace = mapping()
    assert trace["observed_cell_bands"] == {"department": [.4, .6]}
    cells = [cell("AB-7", .42, .52), cell("Ink", .65, .75)]
    before = deepcopy(cells)
    person, proof, changes = complete(trace, cells)
    assert person.department.value == "AB-7" and person.department.state == "uncertain"
    assert changes[0]["field"] == "department" and cells == before
    assert proof["fields"]["department"]["ocr_observations"][0]["ocr_confidence"] == .01


@pytest.mark.parametrize("cells", [[], [cell("A", .42, .46), cell("B", .48, .52)],
                                  [cell("Across", .39, .45)], [cell("Ink", .65, .75)]])
def test_no_guess_for_missing_split_crossing_or_signature_cells(cells):
    person, _, changes = complete(mapping()[2], cells)
    assert person.department.value is None and not changes


def test_completion_does_not_override_surviving_answers_or_explicit_empty():
    for value, state in [("LLM", "read"), ("", "empty")]:
        person, _, changes = complete(mapping()[2], [cell("AB-7", .42, .52)],
                                      existing=TextField(value=value, state=state))
        assert person.department.value == value and not changes


def test_inheritance_is_scoped_and_requires_matching_physical_columns():
    recognized, context, _ = mapping()
    for doc, number, edges, allowed in [("a", 2, recognized["image_column_boundaries"], True),
                                       ("b", 2, recognized["image_column_boundaries"], False),
                                       ("a", 1, recognized["image_column_boundaries"], False),
                                       ("a", 2, [0, .3, .6, 1], False)]:
        _, _, trace = document_bands(dict(image_column_boundaries=edges), [], {}, context,
                                     document_id=doc, page_number=number)
        person, _, changes = complete(trace, [cell("AB-7", .42, .52)])
        assert bool(changes) == allowed
        assert bool(person.department.value) == allowed


def test_no_completion_without_physical_grid_or_person_anchor():
    trace = mapping()[2]
    trace["observed_cell_bands"] = {}
    assert not complete(trace, [cell("AB-7", .42, .52)])[2]
    trace = mapping()[2]
    people, proofs = [Participant(**{f: TextField() for f in TEXT_FIELDS})], [dict(source_row="r1", fields={})]
    assert not complete_observed_cells(people, proofs, [dict(id="r1", native_cells=[cell("AB-7", .42, .52)])], trace)
