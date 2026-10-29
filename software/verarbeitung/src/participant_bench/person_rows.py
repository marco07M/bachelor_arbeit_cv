"""Locate repeated text records, retaining the complete OCR separately for inspection."""

import re
from statistics import median


def select_person_rows(rows):
    by_column = {}
    for index, row in enumerate(rows):
        if not row.get("bbox"):
            continue
        y = (row["bbox"]["y0"] + row["bbox"]["y1"]) / 2
        for cell in row.get("column_texts", []):
            text = cell["text"]
            words = re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", text, re.UNICODE)
            if 2 <= len(words) <= 10 and not any(character.isdigit() for character in text):
                by_column.setdefault(cell["column"], []).append((y, index))
    best, column, spacing = [], None, None
    for candidate, items in by_column.items():
        items.sort()
        for start in range(len(items) - 3):
            step = items[start + 1][0] - items[start][0]
            if not .008 <= step <= .12:
                continue
            run = items[start:start + 2]
            for item in items[start + 2:]:
                if not .65 * step <= item[0] - run[-1][0] <= 1.4 * step:
                    break
                run.append(item)
            if len(run) >= 4 and len(run) > len(best):
                best, column = run, candidate
                spacing = median(b[0] - a[0] for a, b in zip(run, run[1:]))
    if not best:
        return rows, None
    top, bottom = best[0][0] - 1.25 * spacing, best[-1][0] + 1.25 * spacing
    selected = [row for row in rows if row.get("bbox") and top <= (row["bbox"]["y0"] + row["bbox"]["y1"]) / 2 <= bottom]
    return selected, column
