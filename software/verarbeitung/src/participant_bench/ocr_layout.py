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
         round(word["ocr_confidence"])]
        for index, word in enumerate(data["words"])
    ]
    return json.dumps({
        "coordinate_scale": 1000,
        "word_columns": ["id", "text", "x0", "y0", "x1", "y1", "ocr_confidence"],
        "words": words,
        "lines": [
            {"line_id": index, "word_ids": indices,
             "text": " ".join(data["words"][i]["text"] for i in indices)}
            for index, indices in enumerate(line_groups(data), 1)
        ],
    }, ensure_ascii=False, separators=(",", ":"))


def readable_text(data: dict) -> str:
    words = data.get("words", [])
    if not words or any("line" not in word for word in words):
        return data.get("text", "")
    return "\n".join(
        " ".join(word["text"] for word in group)
        for _, group in groupby(words, key=lambda word: tuple(word["line"]))
    )


def model_input(data: dict) -> str:
    return "OCR_LAYOUT_DATA:\n" + compact_layout(data)
