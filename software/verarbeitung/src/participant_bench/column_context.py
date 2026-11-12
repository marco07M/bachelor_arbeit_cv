"""Structural continuation checks for the existing per-document mapping contexts.

Only heading labels, roles and geometry enter this state; never participant values.
The tolerances describe layout compatibility, not OCR confidence or correctness.
"""

from copy import deepcopy
from statistics import median

from .schema import TEXT_FIELDS

VERSION = "document-column-context-v2-verified-continuation"
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


def column_intervals(mapping, profile):
    """Normalized X-intervals per mapped column from measured or native geometry."""
    if not profile or not profile.get("edges"):
        return {}
    edges = profile["edges"]
    intervals = {}
    for field, cols in mapping.items():
        valid = sorted(c for c in cols if isinstance(c, int) and 0 <= c < len(edges) - 1)
        if len(valid) == 1:
            c = valid[0]
            intervals[field] = [edges[c], edges[c + 1]]
        elif field == "signature" and valid:
            intervals[field] = [edges[valid[0]], edges[valid[-1] + 1]]
    return intervals


def compatible(previous, current, *, text_width=None):
    if not previous or not current:
        return False, "missing_measured_column_geometry"
    if previous.get("basis") != current.get("basis"):
        return False, "different_geometry_basis"
    if previous["width"] != current["width"]:
        if (
            text_width is not None
            and 0 < text_width <= current["width"] < previous["width"]
            and max(
                abs(a - b)
                for a, b in zip(previous["edges"][: current["width"] + 1], current["edges"], strict=True)
            )
            <= MAX_EDGE_SHIFT
        ):
            return True, "same_text_column_prefix_geometry"
        return False, "different_column_count"
    if max(abs(a-b) for a, b in zip(previous["edges"], current["edges"], strict=True)) > MAX_EDGE_SHIFT:
        return False, "column_geometry_changed"
    return True, "same_column_count_and_normalized_geometry"


def geometry_check(previous, current, *, text_width=None):
    """Auditable geometry evidence; never a confidence or participant-value check."""
    ok, reason = compatible(previous, current, text_width=text_width)
    comparable = (previous and current and previous.get("basis") == current.get("basis")
                  and len(previous["edges"]) >= len(current["edges"]))
    shifts = ([abs(a-b) for a, b in zip(previous["edges"], current["edges"])] if comparable else [])
    return dict(compatible=ok, reason=reason, allowed_edge_shift=MAX_EDGE_SHIFT,
                max_edge_shift=max(shifts) if shifts else None,
                source_geometry=deepcopy(previous), current_geometry=deepcopy(current))


def mapping_diagnostics(raw):
    """Read saved decisions from existing pipelines, including VLM/Hybrid answers."""
    single = (raw.get("assignment", {}).get("document_column_mapping")
              or raw.get("ocr_layout_analysis", {}).get("mapping_provenance"))
    traces = [single] if single else list(raw.get("structure", {}).get("mapping_diagnostics", []))
    return traces + [response["identity_column_assignment"]["mapping_provenance"]
                     for response in raw.get("responses", [])
                     if response.get("identity_column_assignment", {}).get("mapping_provenance")]


def mapping_reason(trace):
    """Explain saved decisions without recomputing a historical assignment."""
    return {
        "explicit_current_headings": "Eindeutige aktuelle Überschriften haben Vorrang.",
        "same_column_count_and_normalized_geometry": "Gleiche Spaltenzahl und passende gemessene X-Positionen.",
        "same_text_column_prefix_geometry": "Alle Textspalten und ihre gemessenen Grenzen stimmen überein; nur hintere Nichttextspalten fehlen.",
        "missing_measured_column_geometry": "Gemessene Spaltengeometrie fehlt; keine Übernahme.",
        "different_geometry_basis": "Geometriebelege sind nicht vergleichbar; keine Übernahme.",
        "different_column_count": "Abweichende Spaltenzahl; keine Übernahme.",
        "column_geometry_changed": "Spaltengrenzen weichen zu stark ab; keine Übernahme.",
        "ambiguous_current_headings": "Aktuelle Überschriften sind unvollständig oder mehrdeutig; früherer Kontext gesperrt.",
        "document_or_page_order_mismatch": "Andere PDF, falsche Seitenfolge oder alte Kontextversion; keine Übernahme.",
        "no_unambiguous_current_headings": "Keine zuverlässig zuordenbaren Überschriften und kein gültiger Fortsetzungskontext.",
    }.get(trace.get("reason"), "Historischer Grund: " + str(trace.get("reason", "nicht gespeichert")))


def heading_structure(headings):
    """Keep known heading labels/positions, never an entire noisy cell or row."""
    import re

    from .column_headers import ORGANIZATION_ALIASES, normalized_heading
    from .unlimited_assignment import HEADERS

    aliases = {normalized_heading(a) for values in HEADERS.values() for a in values}
    aliases.update(normalized_heading(a) for a in ORGANIZATION_ALIASES)
    aliases.update({"signature", "unterschrift", "signatur", "datum", "date"})
    safe = {}
    for field, labels in headings.items():
        safe[field] = []
        for label in labels:
            original = label if isinstance(label, dict) else dict(text=label)
            title = re.split(r"[\n(]", str(original.get("text", "")), maxsplit=1)[0].strip()
            record = {key: deepcopy(original[key]) for key in ("column", "row", "bbox") if key in original}
            record["text"] = title if normalized_heading(title) in aliases else field
            safe[field].append(record)
    return safe


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
                 geometry=profile, reliability="structural_evidence_only",
                 column_mapping={}, headings={}, geometry_check=None)
    if has_header:
        headings = heading_structure(headings)
        trace.update(column_mapping={key: sorted(cols) for key, cols in mapping.items()}, headings=deepcopy(headings))
        if reliable(mapping) and not ambiguous:
            intervals = column_intervals(mapping, profile)
            text_width = max((c for key in TEXT_FIELDS for c in mapping.get(key, ())), default=-1) + 1
            trace.update(status="updated_on_current_page" if earlier else "detected_on_current_page",
                         source_page=page_number, reason="explicit_current_headings",
                         column_intervals=intervals)
            snapshot = dict(version=VERSION, document_id=document_id, source_page=page_number,
                width=profile["width"] if profile else column_count, text_width=text_width, geometry=profile,
                column_intervals=intervals,
                mapping={key: sorted(cols) for key, cols in mapping.items()}, headings=deepcopy(headings))
            snapshot["column_order"] = [dict(column=c, fields=sorted(key for key, cols in mapping.items() if c in cols))
                                        for c in sorted({c for cols in mapping.values() for c in cols})]
            return mapping, snapshot, trace
        # Ambiguous new headings must block an older layout on subsequent pages too.
        trace["reason"] = "ambiguous_current_headings"
        return mapping, {}, trace
    if earlier:
        check = geometry_check(previous.get("geometry"), profile, text_width=previous.get("text_width"))
        ok, reason = check["compatible"], check["reason"]
        trace.update(reason=reason, source_page=previous["source_page"],
                     geometry_check=check,
                     status="inherited_from_previous_page" if ok else "incompatible_table_structure")
        if ok:
            inherited_mapping = {
                key: {c for c in cols if profile is None or c < profile["width"]}
                for key, cols in previous["mapping"].items()
            }
            inherited_mapping = {key: cols for key, cols in inherited_mapping.items() if cols}
            trace["column_intervals"] = column_intervals(inherited_mapping, profile) or deepcopy(
                previous.get("column_intervals", {})
            )
            trace["inherited_column_intervals"] = deepcopy(previous.get("column_intervals", {}))
            trace.update(column_mapping={key: sorted(cols) for key, cols in inherited_mapping.items()},
                         headings=deepcopy(previous.get("headings", {})))
            return inherited_mapping, previous, trace
        # Rejected geometry must not leak usable intervals to a later OCR fallback.
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
    return edges if len(edges) >= 3 else []
