"""Compact model input and readable fallback text from the complete OCR evidence."""

import json
from itertools import groupby


def line_groups(data: dict) -> list[list[int]]:
    words = data.get("words", [])
    if not words or any("line" not in word for word in words):
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


def with_table_columns(data, image, previous=None):
    """Add geometry only; retain every original word and its ID for independent grounding."""
    from .image_preprocessing import grid_masks
    from .rules import line_positions

    _, _, vertical = grid_masks(image)
    lines = line_positions(vertical, 0, 0.05)
    boundaries = [0.0]
    for value in lines:
        if value - boundaries[-1] > .008:
            boundaries.append(value)
    boundaries.append(1.0)
    enriched = dict(data, physical_columns=boundaries if len(boundaries) >= 5 else [])
    source_rows = []
    for indices in line_groups(data):
        groups = grouped_cells(enriched, indices) if enriched["physical_columns"] else [
            dict(column=0, word_ids=indices, text=" ".join(data["words"][i]["text"] for i in indices))]
        cells = []
        for cell in groups:
            selected = [data["words"][i] for i in cell["word_ids"]]
            cells.append(dict(index=len(cells), column_start=cell["column"], colspan=1, rowspan=1,
                text=cell["text"], kind="native", bbox={key: op(word["bbox"][key] for word in selected)
                    for key, op in (("x0", min), ("y0", min), ("x1", max), ("y1", max))}))
        if cells:
            source_rows.append(dict(id=f"r{len(source_rows)+1}", table_index=0, row_index=len(source_rows), cells=cells,
                column_texts=[dict(column=c["column_start"], text=c["text"]) for c in cells],
                bbox={key: op(c["bbox"][key] for c in cells) for key, op in (("x0", min),("y0", min),("x1", max),("y1", max))}))
    from .person_rows import select_person_rows

    chosen, hint = select_person_rows(source_rows) if enriched["physical_columns"] else (source_rows, None)
    inherited = False
    if hint is None and previous and len(previous["physical_columns"]) == len(enriched["physical_columns"]):
        if all(abs(a-b) < .015 for a,b in zip(previous["physical_columns"], enriched["physical_columns"])):
            hint, inherited = previous["name_column_hint"], True
    chosen = [dict(row, id=f"r{index+1}", original_source_row=row["id"]) for index, row in enumerate(chosen)]
    selected_originals = {row["original_source_row"] for row in chosen}
    enriched.update(text_rows=chosen, name_column_hint=hint, inherited_name_column=inherited,
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
        return "OCR_TEXT_ROWS:\n" + json.dumps(dict(name_column_hint=data.get("name_column_hint"),
            column_boundaries=data.get("physical_columns", []),
            rows=[dict(source_row=row["id"], bbox=row.get("bbox"), cells=row["column_texts"]) for row in data["text_rows"]]),
            ensure_ascii=False, separators=(",", ":"))
    return "OCR_LAYOUT_DATA:\n" + compact_layout(data)
