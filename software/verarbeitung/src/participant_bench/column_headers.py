"""Heading-only normalization. Participant values are never autocorrected."""

import re
import unicodedata

ORGANIZATION_ALIASES = (
    "Abteilung", "Organisation", "Organization", "Organisationseinheit", "Org.-Einheit",
    "Org.", "Bereich", "Department", "Organizational Unit", "Organisational Unit",
    "Kurzzeichen", "Kürzel", "Kuerzel", "Org Unit",
)
VERSION = "organization-headings-v1"


def normalized_heading(text):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", text).casefold()).replace("_", "")


def field_roles(text, aliases=ORGANIZATION_ALIASES):
    from difflib import SequenceMatcher

    from .unlimited_assignment import header_fields

    roles = header_fields(text)
    key = normalized_heading(text)
    if key in {"unterschrift", "signature", "signatur", "signetur"}:
        roles.add("signature")
    if key in {"datum", "date"}:
        roles.add("date")
    title = re.split(r"[\n(]", text, maxsplit=1)[0]
    if key in {normalized_heading(a) for a in aliases} or (
            normalized_heading(title) in {normalized_heading(a) for a in aliases}):
        roles.add("department")
    if not roles and 6 <= len(key) <= 18 and len(text.split()) == 1:
        fuzzy = {"benutzername": {"first_name", "last_name"}, "kurzzeichen": {"department"},
                 "personalnummer": {"personnel_number"}, "unterschrift": {"signature"}}
        matches = [fields for alias, fields in fuzzy.items() if SequenceMatcher(None, key, alias).ratio() >= 0.84]
        if len(matches) == 1:
            roles |= matches[0]
    return roles
