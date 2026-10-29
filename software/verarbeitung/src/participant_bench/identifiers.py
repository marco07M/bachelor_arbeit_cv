"""Comparison-only ID normalization. Never rewrite recognized or reference values."""

import re
import unicodedata


def normalized_user_id(value: str | None, *, ignore_leading_zeros: bool = True) -> str:
    text = unicodedata.normalize("NFC", value or "").strip()
    if ignore_leading_zeros and re.fullmatch(r"[0-9]+", text):
        return text.lstrip("0") or "0"
    return text


def user_id_rule(ignore_leading_zeros: bool) -> str:
    if ignore_leading_zeros:
        return ("Für den Vergleich werden führende Nullen rein numerischer User IDs entfernt "
                "(0047285 = 47285). Originalwerte bleiben erhalten.")
    return "IDs behalten für diesen gespeicherten Vergleich ihre führenden Nullen."
