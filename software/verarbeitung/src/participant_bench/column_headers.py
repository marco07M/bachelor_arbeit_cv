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
    from .unlimited_assignment import header_fields

    roles = header_fields(text)
    if normalized_heading(text) in {"unterschrift", "signature", "signatur", "signetur"}:
        roles.add("signature")
    if normalized_heading(text) in {"datum", "date"}:
        roles.add("date")
    title = re.split(r"[\n(]", text, maxsplit=1)[0]
    if normalized_heading(text) in {normalized_heading(a) for a in aliases} or (
            normalized_heading(title) in {normalized_heading(a) for a in aliases}):
        roles.add("department")
    return roles
