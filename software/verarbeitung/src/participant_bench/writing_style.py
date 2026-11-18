"""Manual participant-level GT annotation; never an extraction field or page inference."""

from typing import Literal

Schriftart = Literal["h", "m", "g"]
STYLES = {"h": "Handschrift", "m": "Maschinenschrift", "g": "Gemischt", "unclassified": "Nicht klassifiziert"}


def validate_schriftart(value):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    if not isinstance(value, str) or value.strip().lower() not in ("h", "m", "g"):
        raise ValueError("schriftart muss h, m, g oder leer sein")
    return value.strip().lower()


def schriftart_column(headers):
    indices = [i for i, h in enumerate(headers) if str(h or "").strip().casefold() == "schriftart"]
    if len(indices) > 1:
        raise ValueError("Mehrdeutige schriftart-Spalten")
    return indices[0] if indices else None
