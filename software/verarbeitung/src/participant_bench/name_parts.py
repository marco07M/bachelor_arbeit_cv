"""Split observed name cells without dictionaries or invented name components."""

import re
import unicodedata

DEFAULT_ORDER = "family_given"


def compact_name(value):
    return re.sub(r"[\s,]+", "", unicodedata.normalize("NFC", value).casefold())


def split_combined_name(value, default_order=DEFAULT_ORDER):
    """A comma separates whole parts. Bare three-part names remain ambiguous."""
    if not value or any(c.isdigit() for c in value):
        return None
    if value.count(",") == 1:
        last, first = (part.strip() for part in value.split(",", 1))
        rule = "explicit_surname_comma_given_name"
    elif "," not in value and len(value.split()) == 2 and default_order != "unknown":
        left, right = value.split()
        first, last = (right, left) if default_order == "family_given" else (left, right)
        rule = "default_name_group_order"
    else:
        return None
    if not all(part and any(c.isalpha() for c in part) for part in (first, last)):
        return None
    return first, last, rule


def matching_name_cells(cells, first, last):
    """Use only the cell completely covered by the model's observed name parts."""
    if not first or not last:
        return []
    parts = [compact_name(first), compact_name(last)]
    return [cell for cell in cells if cell.get("text")
            and compact_name(cell["text"]) in ("".join(parts), "".join(reversed(parts)))]


def matching_comma_cells(cells, first, last):
    return [cell for cell in matching_name_cells(cells, first, last)
            if split_combined_name(cell["text"], "unknown")]
