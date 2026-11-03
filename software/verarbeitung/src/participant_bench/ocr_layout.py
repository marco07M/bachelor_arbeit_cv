"""Compact model input and readable fallback text from the complete OCR evidence."""

import json
from itertools import groupby


def line_groups(data: dict) -> list[list[int]]:
    words = data.get("words", [])
    if not words or any(not isinstance(word.get("line"), (list, tuple)) or len(word["line"]) != 3 for word in words):
        return []
    return [[index for index, _ in group] for _, group in groupby(
        enumerate(words), key=lambda item: tuple(item[1]["line"])
    )]


def compact_layout(data: dict) -> str:
    # Only position/confidence precision is reduced in the prompt; original OCR stays in the run.
    words = [
        [index, word["text"],
         *(round(word["bbox"][axis] * 1000) for axis in ("x0", "y0", "x1", "y1")),
         round(word["ocr_confidence"]) if word["ocr_confidence"] is not None else None]
        for index, word in enumerate(data["words"])
    ]
    return json.dumps({
        "coordinate_scale": 1000,
        "word_columns": ["id", "text", "x0", "y0", "x1", "y1", "ocr_confidence"],
        "words": words,
        **({"physical_columns": data["physical_columns"]} if data.get("physical_columns") else {}),
        "lines": [
            {"line_id": index, "word_ids": indices,
             "text": " ".join(data["words"][i]["text"] for i in indices),
             **({"cells": grouped_cells(data, indices)} if data.get("physical_columns") else {})}
            for index, indices in enumerate(line_groups(data), 1)
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def grouped_cells(data, indices):
    columns = data["physical_columns"]
    result = []
    for index, (left, right) in enumerate(zip(columns, columns[1:])):
        members = [i for i in indices if left <= (data["words"][i]["bbox"]["x0"] + data["words"][i]["bbox"]["x1"]) / 2 < right]
        if members:
            result.append(dict(column=index, word_ids=members, text=" ".join(data["words"][i]["text"] for i in members)))
    return result


def with_table_columns(data, image, previous=None, *, document_id=None, page_number=None, row_policy="pattern"):
    """Add geometry only; retain every original word and its ID for independent grounding."""
    from .column_context import geometry, image_boundaries, resolve
    from .column_headers import field_roles

    boundaries = image_boundaries(image)
    enriched = dict(data, physical_columns=boundaries)
    source_rows = []
    for indices in line_groups(data):
        groups = grouped_cells(enriched, indices) if enriched["physical_columns"] else [
            dict(column=0, word_ids=indices, text=" ".join(data["words"][i]["text"] for i in indices))]
        cells = []
        for cell in groups:
            selected = [data["words"][i] for i in cell["word_ids"]]
            cells.append(dict(index=len(cells), column_start=cell["column"], colspan=1, rowspan=1,
                text=cell["text"], word_ids=cell["word_ids"], kind="native", bbox={key: op(word["bbox"][key] for word in selected)
                    for key, op in (("x0", min), ("y0", min), ("x1", max), ("y1", max))}))
        if cells:
            source_rows.append(dict(id=f"r{len(source_rows)+1}", table_index=0, row_index=len(source_rows), cells=cells,
                column_texts=[dict(column=c["column_start"], text=c["text"]) for c in cells],
                bbox={key: op(c["bbox"][key] for c in cells) for key, op in (("x0", min),("y0", min),("x1", max),("y1", max))}))
    from .person_rows import select_person_rows

    chosen, hint = select_person_rows(source_rows) if enriched["physical_columns"] else (source_rows, None)
    mapping, headings, header_rows = {}, {}, []
    for row in source_rows:
        classified = [(c, field_roles(c["text"])) for c in row["cells"]]
        found = set().union(*(roles for _, roles in classified)) if classified else set()
        if boundaries and found & {"first_name", "last_name"} and len(found) >= 2:
            header_rows.append(row["id"])
            mapping, headings = {}, {}
            for cell, roles in classified:
                for field in roles:
                    mapping.setdefault(field, set()).add(cell["column_start"])
                    headings.setdefault(field, []).append(dict(text=cell["text"], column=cell["column_start"], bbox=cell["bbox"]))
    profile = geometry(len(boundaries)-1, boundaries=boundaries) if boundaries else None
    mapping, context, trace = resolve(mapping, headings, profile,
        (previous or {}).get("column_mapping_context"), document_id=document_id, page_number=page_number,
        has_header=bool(header_rows))
    inherited = trace["status"] == "inherited_from_previous_page"
    name_columns = set(mapping.get("first_name", ())) | set(mapping.get("last_name", ()))
    if len(name_columns) == 1:
        hint = next(iter(name_columns))
    elif mapping:
        hint = None  # Separate name columns must not be collapsed into a guessed combined cell.
    heuristic_ids = {row["id"] for row in chosen}
    if row_policy not in ("pattern", "all"):
        raise ValueError("Unknown OCR row selection policy")
    if row_policy == "all" or inherited:
        chosen = source_rows
    chosen = [dict(row, selection_hint="person_pattern" if row["id"] in heuristic_ids else "unclassified_observation")
              for row in chosen]
    chosen = [dict(row, id=f"r{index+1}", original_source_row=row["id"]) for index, row in enumerate(chosen)]
    selected_originals = {row["original_source_row"] for row in chosen}
    enriched.update(text_rows=chosen, name_column_hint=hint, inherited_name_column=inherited,
                    column_mapping={key: sorted(cols) for key, cols in mapping.items()},
                    column_mapping_context=context, mapping_provenance=trace,
                    selection_diagnostics=dict(source_rows=len(source_rows), heuristic_rows=len(heuristic_ids),
                        model_input_rows=len(chosen), omitted_rows=len(source_rows)-len(chosen), policy=row_policy),
                    all_text_rows=source_rows, row_selection_policy=row_policy,
                    unassigned_word_ids=[i for i in range(len(data.get("words", []))) if not any(
                        i in cell.get("word_ids", []) for row in source_rows for cell in row["cells"])],
                    context_rows=[row["id"] for row in source_rows if row["id"] not in selected_originals])
    return enriched


def readable_text(data: dict) -> str:
    words = data.get("words", [])
    if not words or any("line" not in word for word in words):
        return data.get("text", "")
    return "\n".join(
        " ".join(word["text"] for word in group)
        for _, group in groupby(words, key=lambda word: tuple(word["line"]))
    )


def model_input(data: dict) -> str:
    if "text_rows" in data:
        payload = dict(name_column_hint=data.get("name_column_hint"),
            column_mapping=data.get("column_mapping", {}), mapping_provenance=data.get("mapping_provenance"),
            column_boundaries=data.get("physical_columns", []),
            rows=[dict(source_row=row["id"], bbox=row.get("bbox"), cells=row["column_texts"],
                       **(dict(selection_hint=row.get("selection_hint", "unclassified_observation"))
                          if data.get("row_selection_policy") == "all" else {})) for row in data["text_rows"]])
        if data.get("unassigned_word_ids") or data.get("row_selection_policy") == "all":
            payload["unassigned_observations"] = [dict(word_id=i, text=data["words"][i]["text"],
                bbox=data["words"][i].get("bbox"), ocr_confidence=data["words"][i].get("ocr_confidence"))
                for i in data.get("unassigned_word_ids", [])]
        return "OCR_TEXT_ROWS:\n" + json.dumps(payload,
            ensure_ascii=False, separators=(",", ":"))
    return "OCR_LAYOUT_DATA:\n" + compact_layout(data)
