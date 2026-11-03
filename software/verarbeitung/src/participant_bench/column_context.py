"""Structural continuation checks for the existing per-document mapping contexts.

Only heading labels, roles and geometry enter this state; never participant values.
The tolerances describe layout compatibility, not OCR confidence or correctness.
"""

from copy import deepcopy
from statistics import median

from .schema import TEXT_FIELDS

VERSION = "document-column-context-v1"
MAX_EDGE_SHIFT = .035


def geometry(width, rows=(), boundaries=None):
    """Use measured grid lines or native single-column cells, never guessed columns."""
    if not isinstance(width, int) or width < 2:
        return None
    if any(row.get("grid_width", width) != width for row in rows):
        return None
    if boundaries is not None:
        edges = list(boundaries)
        if len(edges) != width + 1 or any(not 0 <= x <= 1 for x in edges) or any(
                b - a <= .003 for a, b in zip(edges, edges[1:])):
            return None
        return dict(width=width, edges=edges, basis="measured_grid_lines")
    cells = [c for row in rows for c in row["cells"] if c.get("bbox") and
             c.get("colspan", 1) == c.get("rowspan", 1) == 1]
    intervals = []
    for index in range(width):
        selected = [c["bbox"] for c in cells if c["column_start"] == index]
        if not selected:
            return None
        intervals.append((median(c["x0"] for c in selected), median(c["x1"] for c in selected)))
    if any(right <= left for left, right in intervals) or any(
            a[1] > b[0] + .015 for a, b in zip(intervals, intervals[1:])):
        return None
    edges = [intervals[0][0], *((a[1] + b[0]) / 2 for a, b in zip(intervals, intervals[1:])), intervals[-1][1]]
    return dict(width=width, edges=edges, basis="native_cell_geometry")


def compatible(previous, current):
    if not previous or not current:
        return False, "missing_measured_column_geometry"
    if previous["width"] != current["width"]:
        return False, "different_column_count"
    if previous.get("basis") != current.get("basis"):
        return False, "different_geometry_basis"
    if max(abs(a-b) for a, b in zip(previous["edges"], current["edges"], strict=True)) > MAX_EDGE_SHIFT:
        return False, "column_geometry_changed"
    return True, "same_column_count_and_normalized_geometry"


def reliable(mapping):
    text = {key: cols for key, cols in mapping.items() if key in TEXT_FIELDS and cols}
    collisions = [{key for key, cols in text.items() if column in cols}
                  for column in {c for cols in text.values() for c in cols}]
    return (bool(text.keys() & {"first_name", "last_name"}) and len(text) >= 2
            and all(len(cols) == 1 for cols in text.values())
            and all(len(keys) == 1 or keys == {"first_name", "last_name"} for keys in collisions))


def project_bands(bands, previous, current):
    """Move heading bands along measured corresponding edges, without new roles."""
    old, new = previous["edges"], current["edges"]
    def project(value):
        for index, (left, right) in enumerate(zip(old, old[1:])):
            if value <= right:
                return max(0., min(1., new[index] + (value-left) / (right-left) * (new[index+1]-new[index])))
        return value + new[-1] - old[-1]
    return {field: [project(left), project(right)] for field, (left, right) in bands.items()}


def resolve(mapping, headings, profile, previous=None, *, document_id=None, page_number=None, has_header=False,
            column_count=None, ambiguous=False):
    """Current headings win; inheritance requires scoped, earlier, compatible evidence.

    Standalone callers may omit page metadata for a current-page extraction, but
    cannot inherit that anonymous state into another page.
    """
    previous = deepcopy(previous or {})
    scoped = (previous.get("version") == VERSION and document_id is not None
              and previous.get("document_id") == document_id)
    earlier = (scoped and isinstance(page_number, int) and
               isinstance(previous.get("source_page"), int) and previous["source_page"] < page_number)
    trace = dict(version=VERSION, document_id=document_id, page_number=page_number,
                 source_page=None, status="no_reliable_mapping", reason="no_unambiguous_current_headings",
                 geometry=profile, reliability="structural_evidence_only")
    if has_header:
        if reliable(mapping) and not ambiguous:
            trace.update(status="updated_on_current_page" if earlier else "detected_on_current_page",
                         source_page=page_number, reason="explicit_current_headings")
            snapshot = dict(version=VERSION, document_id=document_id, source_page=page_number,
                width=profile["width"] if profile else column_count, geometry=profile,
                mapping={key: sorted(cols) for key, cols in mapping.items()}, headings=deepcopy(headings))
            snapshot["column_order"] = [dict(column=c, fields=sorted(key for key, cols in mapping.items() if c in cols))
                                        for c in sorted({c for cols in mapping.values() for c in cols})]
            return mapping, snapshot, trace
        # Ambiguous new headings must block an older layout on subsequent pages too.
        trace["reason"] = "ambiguous_current_headings"
        return mapping, {}, trace
    if earlier:
        ok, reason = compatible(previous.get("geometry"), profile)
        trace.update(reason=reason, source_page=previous["source_page"],
                     status="inherited_from_previous_page" if ok else "incompatible_table_structure")
        if ok:
            return {key: set(cols) for key, cols in previous["mapping"].items()}, previous, trace
    elif previous:
        trace["reason"] = "document_or_page_order_mismatch"
    return {}, previous if scoped else {}, trace


def image_boundaries(image):
    """The same grid detector already used by Tesseract layout enrichment."""
    from .image_preprocessing import grid_masks
    from .rules import line_positions

    _, _, vertical = grid_masks(image)
    edges = [0.0]
    for value in line_positions(vertical, 0, .05):
        if value - edges[-1] > .008 and value < .992:
            edges.append(value)
    edges.append(1.0)
    return edges if len(edges) >= 5 else []
