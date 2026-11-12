"""Reuse selection inventory columns for manually reviewed strata and leakage-safe course groups."""

import csv
from collections import defaultdict
from pathlib import Path

from ..io import file_hash, write_csv
from .evaluation import map_documents

STRATA = {"printed", "handwritten", "mixed", "unknown"}
PHASES = {"development", "pilot", "test", "unknown"}
FLAGS = {
    "clean",
    "low_contrast",
    "skew",
    "shadow",
    "cropped",
    "wrapped_text",
    "headerless_continuation",
    "multiple_pages",
    "variable_layout",
}


def document_inventory(manifest, known):
    mapping, rows, _ = map_documents(manifest, known)
    return mapping, [dict(document_id=r["document_id"], class_id=r["class_id"] or "unknown") for r in rows]


def template(manifest, known, output):
    if output.exists():
        raise ValueError("Metadatendatei existiert bereits")
    _, documents = document_inventory(manifest, known)
    rows = [
        dict(
            d,
            dependency_group="",
            grouping_reviewed="false",
            prior_use="unknown",
            partition="unknown",
            stratum="unknown",
            quality_flags="",
        )
        for d in documents
    ]
    write_csv(output, rows)
    return output


def load_metadata(manifest, known, path=None):
    mapping, documents = document_inventory(manifest, known)
    supplied = {}
    if path:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key = row.get("document_id", "")
                if not key or key in supplied:
                    raise ValueError("Dokumentmetadaten fehlen oder sind doppelt")
                supplied[key] = row
        if set(supplied) - {d["document_id"] for d in documents}:
            raise ValueError("Metadaten enthalten fremde Dokumente")
    groups, courses = defaultdict(set), defaultdict(set)
    records = {}
    for doc in documents:
        key, course = doc["document_id"], doc["class_id"]
        row = supplied.get(key, {})
        reviewed = row.get("grouping_reviewed", "false").lower() == "true"
        group = row.get("dependency_group", "").strip()
        if reviewed and not group:
            raise ValueError("Geprüfte Gruppe benötigt eine Kennung")
        stratum, phase = row.get("stratum", "unknown"), row.get("partition", "unknown") or "unknown"
        flags = set(filter(None, row.get("quality_flags", "").split(";")))
        if stratum not in STRATA or phase not in PHASES or flags - FLAGS:
            raise ValueError("Unbekanntes Schriftstratum, Phase oder Qualitätsmerkmal")
        if row.get("class_id") and row["class_id"] != course:
            raise ValueError("Metadaten-Schulung widerspricht dem Eingabemanifest")
        prior = row.get("prior_use", "unknown")
        if (
            prior not in ("unknown", "unused", "development")
            or prior == "development"
            and phase != "development"
        ):
            raise ValueError("Vorbenutzte Entwicklungsdaten dürfen nicht Pilot oder Test sein")
        # Course is only a structural fallback, NEVER a claim of checked independence.
        group = "manual:" + group if group else "course:" + course
        groups[group].add(phase)
        courses[course].add((group, phase))
        records[key] = dict(
            doc,
            dependency_group=group,
            grouping_reviewed=reviewed,
            prior_use=prior,
            partition=phase,
            stratum=stratum,
            quality_flags=sorted(flags),
            features_reviewed=bool(row),
        )
    if any(len(v) > 1 for v in groups.values()) or any(len(v) > 1 for v in courses.values()):
        raise ValueError("Schulung oder Abhängigkeitsgruppe überschreitet Gruppen/Phasen")
    return (
        records,
        dict(
            path=str(Path(path).resolve()) if path else None,
            sha256=file_hash(path) if path else None,
            reviewed_documents=sum(r["grouping_reviewed"] for r in records.values()),
            documents=len(records),
        ),
        mapping,
    )


def course_metadata(course, documents, manifest):
    """Course-level reference cannot localize quality to one PDF in a multi-PDF course."""
    members = [d for d in documents.values() if d["class_id"] == course]

    def common(name):
        values = {d[name] for d in members}
        return (
            next(iter(values))
            if len(values) == 1
            else "unknown"
            if "unknown" in values
            else "heterogeneous_course"
        )

    flags_known = bool(members) and all(d["features_reviewed"] for d in members)
    flags = set(f for d in members for f in d["quality_flags"])
    counts = [
        sum(p.get("document_id") == d["document_id"] for p in manifest.get("pages", [])) for d in members
    ]
    return dict(
        class_id=course,
        documents=[d["document_id"] for d in members],
        pdf_count=len(members),
        dependency_group=common("dependency_group"),
        partition=common("partition"),
        stratum=common("stratum"),
        grouping_reviewed=all(d["grouping_reviewed"] for d in members),
        prior_use_reviewed=all(d["prior_use"] != "unknown" for d in members),
        headerless="yes"
        if "headerless_continuation" in flags
        else "not_marked"
        if flags_known
        else "unknown",
        variable_layout="yes" if "variable_layout" in flags else "not_marked" if flags_known else "unknown",
        image_quality="degraded"
        if flags & {"low_contrast", "skew", "shadow", "cropped"}
        else "clean"
        if flags_known and all("clean" in d["quality_flags"] for d in members)
        else "unknown",
        multipage_pdf="yes"
        if any(n > 1 for n in counts)
        else "no"
        if counts and all(n == 1 for n in counts)
        else "unknown",
    )
