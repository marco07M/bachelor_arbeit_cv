"""Freeze reviewed document groups before selection; final test PDFs are never rendered here."""

import csv
import importlib.metadata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .calibration.dataset import assign_groups
from .io import digest, file_hash, read_json, write_csv, write_json
from .roster_benchmark.evaluation import identify_course
from .selection_config import load_policy

PARTITIONS = {"development", "pilot", "test"}
FLAGS = {"low_contrast", "skew", "shadow", "cropped", "wrapped_text", "headerless_continuation",
         "multiple_pages", "variable_layout", "clean"}


def implementation_identity():
    root = Path(__file__).parent
    software = root.parents[2]
    sources = {str(p.relative_to(root)): file_hash(p) for p in root.rglob("*.py")}
    sources.update({"worker/" + p.name: file_hash(p) for p in (software / "structure_runtime").glob("*.py")})
    return dict(sources=sources,
                locks={name: file_hash(software / name / "uv.lock") for name in
                       (".", "docling_runtime", "paddle_structure_runtime")},
                packages={name: importlib.metadata.version(name) for name in
                          ("pydantic", "pyyaml", "scipy", "pymupdf", "openpyxl")})


def prompt_identity():
    from .models import extraction_prompt_snapshot

    return extraction_prompt_snapshot()


def inventory(folder: Path, output: Path):
    if output.exists():
        raise ValueError("Inventar existiert bereits")
    if not folder.is_dir():
        raise ValueError("PDF-Eingabeordner fehlt")
    rows, seen = [], {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink() or path.suffix.lower() != ".pdf" or not path.is_file():
            continue
        document_id, course = file_hash(path), identify_course(str(path), set())
        if document_id in seen:
            if seen[document_id] != course:
                raise ValueError("Identische PDF unter verschiedenen Schulungs-IDs")
            continue
        seen[document_id] = course
        rows.append(dict(document_id=document_id, path=str(path.resolve()), class_id=course,
                         dependency_group=course, grouping_reviewed="false", prior_use="unknown",
                         stratum="unassigned", quality_flags="", partition=""))
    if not rows:
        raise ValueError("Keine PDFs gefunden")
    write_csv(output, rows)
    return output


def select_groups(groups, target, seed):
    """Round-robin over reviewed strata, stable hash order within strata; never split a group."""
    strata = defaultdict(list)
    for group, docs in groups.items():
        strata[tuple(sorted({d["stratum"] for d in docs}))].append(group)
    for values in strata.values():
        values.sort(key=lambda g: digest([seed, g]))
    selected, count = [], 0
    while count < target and any(strata.values()):
        for stratum in sorted(strata):
            if strata[stratum] and count < target:
                group = strata[stratum].pop(0)
                selected.append(group)
                count += len(groups[group])
    return selected


def freeze(inventory_path: Path, policy_path: Path, output: Path):
    if output.exists():
        raise ValueError("Stichprobenplan existiert bereits; neue Version verwenden")
    policy, profiles = load_policy(policy_path)
    with inventory_path.open(encoding="utf-8-sig", newline="") as stream:
        documents = list(csv.DictReader(stream))
    if not documents or len({d["document_id"] for d in documents}) != len(documents):
        raise ValueError("Leeres Inventar oder doppelte Dokument-IDs")
    groups, courses = defaultdict(list), defaultdict(set)
    for doc in documents:
        if doc.get("grouping_reviewed", "").lower() != "true" or not doc.get("dependency_group", "").strip():
            raise ValueError("Schulungs-/Vorlagen-/Personenabhängigkeiten manuell prüfen und grouping_reviewed=true setzen")
        if doc.get("prior_use") not in ("development", "unused"):
            raise ValueError("Frühere Nutzung als development oder unused dokumentieren")
        if doc.get("stratum") not in ("printed", "mixed", "handwritten"):
            raise ValueError("Schriftstratum printed, mixed oder handwritten manuell angeben")
        flags = set(filter(None, doc.get("quality_flags", "").split(";")))
        if not flags or flags - FLAGS:
            raise ValueError("Mindestens ein gültiges Qualitätsmerkmal erforderlich")
        if not doc.get("class_id") or doc.get("partition", "") not in PARTITIONS | {""}:
            raise ValueError("Schulungs-ID oder Partition ungültig")
        path = Path(doc["path"])
        if not path.is_file() or file_hash(path) != doc["document_id"]:
            raise ValueError("PDF stimmt nicht mit stabiler SHA256-ID überein")
        if identify_course(str(path), {doc["class_id"]}) != doc["class_id"]:
            raise ValueError("Dateiname passt nicht zur Schulungs-ID")
        doc["path"] = str(path.resolve())
        groups[doc["dependency_group"]].append(doc)
        courses[doc["class_id"]].add(doc["dependency_group"])
    if any(len(values) != 1 for values in courses.values()):
        raise ValueError("Dieselbe Schulung muss vollständig in einer Dokumentgruppe bleiben")
    assignment, automatic = {}, []
    for group, docs in groups.items():
        explicit = {d["partition"] for d in docs if d["partition"]}
        if any(d["prior_use"] == "development" for d in docs):
            explicit.add("development")
        if len(explicit) > 1:
            raise ValueError("Gruppe überschreitet Partitionen oder verwendete Entwicklungsdaten wurden umdeklariert")
        if explicit:
            assignment[group] = explicit.pop()
        else:
            automatic.extend(docs)
    if automatic:
        # Reuse the existing grouped, stratified splitter, with validation renamed pilot.
        split = assign_groups(automatic, policy.seed, policy.split_ratios)
        assignment.update({g: "pilot" if s == "validation" else s for g, s in split.items()})
    selected = select_groups({g: docs for g, docs in groups.items() if assignment[g] == "pilot"},
                             policy.target_lists, policy.seed)
    for doc in documents:
        doc["partition"] = assignment[doc["dependency_group"]]
        doc["selected"] = doc["partition"] == "development" or doc["dependency_group"] in selected
    pilot = [d for d in documents if d["partition"] == "pilot" and d["selected"]]
    plan = dict(version=1, created_at=datetime.now(timezone.utc).isoformat(),
                policy=policy.model_dump(), profiles=profiles, documents=documents,
                inventory_sha256=file_hash(inventory_path), policy_sha256=file_hash(policy_path),
                implementation=implementation_identity(), prompts=prompt_identity(),
                partitions=dict(Counter(d["partition"] for d in documents)),
                pilot_lists=len(pilot), pilot_groups=len(selected),
                pilot_strata=dict(Counter(d["stratum"] for d in pilot)),
                missing_pilot_strata=sorted(set(policy.required_strata) - {d["stratum"] for d in pilot}),
                note="Prior development use forces development. Pilot selection uses metadata, never model scores.")
    plan["seal"] = digest(plan)
    write_json(output, plan)
    return output


def load_plan(path: Path, scope="pilot"):
    plan = read_json(path)
    if plan.get("seal") != digest({k: v for k, v in plan.items() if k != "seal"}):
        raise ValueError("Eingefrorener Plan wurde verändert")
    if plan["implementation"] != implementation_identity():
        raise ValueError("Code, Lockdateien oder Auswertungspakete seit dem Einfrieren verändert; neuen Plan versionieren")
    if scope not in ("development", "pilot"):
        raise ValueError("Finale Testdaten dürfen nicht zur Verfahrensauswahl verwendet werden")
    selected = [d for d in plan["documents"] if d["partition"] == scope and d["selected"]]
    if not selected:
        raise ValueError("Keine Dokumente für diese Auswahlphase; vorhandene Entwicklungsdaten nicht als Pilot umdeklarieren")
    for doc in selected:
        if file_hash(Path(doc["path"])) != doc["document_id"]:
            raise ValueError("Ausgewählte PDF seit dem Einfrieren verändert")
    return plan, selected
