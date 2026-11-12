"""Selection orchestration around the existing extraction and roster evaluators, not a new metric pipeline."""

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from .config import Config
from .io import digest, file_hash, read_json, read_jsonl, write_csv, write_json
from .roster_benchmark.evaluation import evaluate_run, identify_course
from .roster_benchmark.matching import Prediction
from .roster_benchmark.metrics import aggregate, course_metrics
from .roster_benchmark.references import read_reference, saved_reference
from .schema import PageResult
from .selection_config import SelectionPolicy, matrix
from .selection_sample import load_plan


def bindings(values):
    result = {}
    for value in values or []:
        key, separator, path = value.partition("=")
        if not separator or not key or not path or key in result:
            raise ValueError("Quellen eindeutig als KANDIDAT=PFAD angeben")
        result[key] = Path(path).resolve()
    return result


def profile_identity(data, candidate):
    config = Config.model_validate(data)
    method = candidate.method
    models = (["ocr_llm"] if method in ("ocr_llm", "paddle_llm") else
              ["vlm"] if method in ("vlm", "ocr_vlm") or candidate.role == "hybrid" else [])
    structure = (config.structures.get("paddle_llm") if method == "ocr_vlm" else config.structures.get(method))
    return dict(seed=config.seed, pdf=config.pdf.model_dump(),
                ocr=config.ocr.model_dump() if method in ("ocr_raw", "ocr_llm", "docling") else None,
                rules=config.rules.model_dump() if method == "ocr_llm" else None,
                signature=config.signature.model_dump(),
                models={name: config.models[name].model_dump() for name in models},
                structure=structure.model_dump() if structure else None)


def recommend(policy, eligibility, rows, plan, scope):
    """Preserve architecture roles. Within a role use strict exact F1, coverage, then stable ID."""
    lookup = {r["candidate"]: r for r in rows}
    selected, reasons = [], []
    for role in ("structure", "ocr_llm", "vision"):
        candidates = [key for key, c in policy.candidates.items() if c.role == role
                      and eligibility[key]["eligibility"] not in ("excluded", "diagnostic_only")]
        if not candidates:
            reasons.append(f"missing_architecture:{role}")
            continue
        available = [key for key in candidates if lookup[key].get("original_exact_f1") is not None
                     and lookup[key]["status"] == "complete"]
        if available:
            winner = min(available, key=lambda key: (-lookup[key]["original_exact_f1"],
                         -lookup[key].get("field_coverage", 0), key))
        else:
            winner = sorted(candidates)[0]
            reasons.append(f"no_complete_evidence:{role}")
        selected.append(winner)
        if eligibility[winner]["eligibility"] != "eligible":
            reasons.append(f"stage_a_open:{winner}")
    if scope != "pilot":
        reasons.append("development_replay_is_not_independent_pilot")
    if plan["pilot_lists"] < policy.minimum_pilot_lists:
        reasons.append("insufficient_pilot_lists")
    if plan["pilot_groups"] < policy.minimum_pilot_groups:
        reasons.append("insufficient_independent_groups")
    if plan["missing_pilot_strata"]:
        reasons.append("missing_required_strata")
    # A competitor cannot be discarded as inferior just because its measurement is absent.
    if any(lookup[k]["status"] != "complete" for k, c in policy.candidates.items()
           if c.role in ("structure", "ocr_llm", "vision") and eligibility[k]["eligibility"] != "excluded"):
        reasons.append("incomplete_main_candidate_comparison")
    for key in selected:
        reasons.extend(f"{key}:{reason}" for reason in lookup[key].get("limitations", []))
    excluded = {}
    for key, candidate in policy.candidates.items():
        if key in selected:
            continue
        excluded[key] = ("Diagnostic OCR baseline; no structured field ranking" if candidate.role == "diagnostic" else
                         "Optional experiment; excluded from the three main architecture roles" if candidate.role == "hybrid"
                         else "Alternative within the same architecture; decision is provisional unless pilot-supported")
    return dict(status="provisional" if reasons else "pilot_supported_recommendation",
                main_methods=selected, optional_experiment="ocr_vlm" if "ocr_vlm" in policy.candidates else None,
                reasons=sorted(set(reasons)), excluded_from_main=excluded,
                rule="One structure baseline, one OCR+LLM and one direct VLM; within role original-role exact field F1 "
                     "on fixed reference-assisted pairs. "
                     "Ties: field coverage then stable candidate ID. No cross-architecture leaderboard.",
                hybrid_reason="ocr_vlm versus vlm isolates added Paddle hints with the same VLM. "
                              "Docling-VLM changes selection and merge rules too, so it is a separate, broader experiment.")


def compare(plan_path, output, sources=None, comparisons=None, *, scope="pilot", reference=None, benchmark_path=None):
    plan, documents = load_plan(plan_path, scope)
    policy = SelectionPolicy.model_validate(plan["policy"])
    sources, comparisons = sources or {}, comparisons or {}
    if set(sources) & set(comparisons) or (set(sources) | set(comparisons)) - set(policy.candidates):
        raise ValueError("Doppelte oder unbekannte Kandidatenquellen")
    if not sources and not comparisons:
        raise ValueError("Mindestens einen vorhandenen Lauf oder Vergleich angeben")
    if output.exists():
        raise ValueError("Neuen Ergebnisordner verwenden")
    ids, courses = {d["document_id"] for d in documents}, {d["class_id"] for d in documents}
    final_ids = {d["document_id"] for d in plan["documents"] if d["partition"] == "test"}
    frozen, reference_hash, reference_file, benchmark = None, None, None, None
    source_artifacts = {}
    for key, report in comparisons.items():
        source, data, ref_hash, ref_file, config = saved_reference(report)
        # Restrict references to entire selected courses, never incomplete course fragments.
        data.people = [p for p in data.people if p.class_id in courses]
        if frozen is not None and (digest([vars(p) for p in data.people]) != digest([vars(p) for p in frozen.people])
                                   or config.reference != benchmark.reference or data.columns != frozen.columns):
            raise ValueError("Vergleiche verwenden unterschiedliche eingefrorene Referenzen/Referenzregeln")
        frozen, reference_hash, reference_file, benchmark = data, ref_hash, ref_file, config
        sources[key] = source
        source_artifacts[key] = {p.name: file_hash(p) for p in (report / n for n in
                                  ("identity.json", "config.json", "reference_snapshot.json", "metrics.json"))}
    if not comparisons:
        if reference is None or benchmark_path is None:
            raise ValueError("Für Extraktionsläufe --reference und --benchmark-config angeben")
        from .roster_benchmark.config import load_config

        benchmark = load_config(benchmark_path)
        reference_hash, reference_file = file_hash(reference), reference
        frozen = read_reference(reference, benchmark.reference)
        if file_hash(reference) != reference_hash:
            raise ValueError("Referenz während des Einlesens verändert")
        frozen.people = [p for p in frozen.people if p.class_id in courses]
    elif reference is not None or benchmark_path is not None:
        raise ValueError("Bei gespeicherten Vergleichen deren eingefrorene Referenz verwenden")
    if {p.class_id for p in frozen.people} != courses:
        raise ValueError("Für jede ausgewählte Schulung muss eine Referenz vorliegen")
    # Freeze comparison semantics across all sources, even when historical reports differ.
    benchmark = benchmark.model_copy(deep=True)
    benchmark.matching.mode = "best_fit"
    benchmark.matching.ignore_leading_user_id_zeros = True
    benchmark.matching.score_uncertain_values = True
    rows, field_rows, timing_rows, identities, shared_images, quality = [], [], [], {}, {}, {}
    output.mkdir(parents=True, exist_ok=False)
    for key, candidate in policy.candidates.items():
        row = dict(candidate=key, role=candidate.role, status="missing", documents_expected=len(ids),
                   documents_processed=0, pages_expected=None, pages_successful=0, limitations=[])
        if key not in sources:
            rows.append(row)
            continue
        source = sources[key].resolve()
        manifest = read_json(source / "manifest.json")
        present = {p["sha256"] for p in manifest["inputs"] if p["kind"] == "pdf"}
        if final_ids & present:
            raise ValueError("Quelllauf enthält finale Testdokumente und ist für die Auswahl gesperrt")
        if not ids <= present:
            # Do not silently intersect candidate-specific subsets and shrink the denominator.
            raise ValueError("Alle Kandidaten benötigen dieselben ausgewählten Dokumente im Eingabemanifest")
        if any(p["kind"] == "pdf" and p["sha256"] not in ids and
               identify_course(p["path"], courses) in courses for p in manifest["inputs"]):
            raise ValueError("Schulung im Quelllauf enthält weitere, nicht ausgewählte PDFs; ganze Schulung aufnehmen")
        summary = read_json(source / "summary.json")
        if candidate.method not in summary:
            rows.append(row)
            continue
        config_path = source / "config.yaml"
        actual = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        expected = plan["profiles"][key]
        actual_assist = actual.get("structures", {}).get("docling", {}).get("vlm_assist", False)
        if candidate.method == "docling" and bool(actual_assist) != (candidate.role == "hybrid"):
            raise ValueError("Docling-Baseline und Docling-VLM-Assist dürfen nicht verwechselt werden")
        if any(m.get("backend", "local") != "local" for m in actual.get("models", {}).values()):
            raise ValueError("API-Läufe gehören nicht in die lokale Auswahlstudie")
        if profile_identity(actual, candidate) != profile_identity(expected, candidate):
            row["limitations"].append("profile_differs_from_frozen_plan")
        prompts_path = source / "prompts.json"
        if not prompts_path.is_file():
            row["limitations"].append("missing_saved_prompt_identity")
        else:
            prompts = read_json(prompts_path)
            if any(prompts.get(name) != value for name, value in plan["prompts"].items()):
                row["limitations"].append("prompts_differ_from_frozen_plan")
        path = source / candidate.method / "extractions.jsonl"
        pages = [p for p in read_jsonl(path) if p["document_id"] in ids] if path.is_file() else []
        expected_pages = {(p["document_id"], p["page_number"]) for p in manifest["pages"] if p["document_id"] in ids}
        successful = {(p["document_id"], p["page_number"]) for p in pages
                      if p["status"] in ("success", "partial") and (p["parse_status"] == "valid" or
                         candidate.role == "diagnostic" and p.get("output_kind") == "ocr_text")}
        row.update(documents_processed=len({p["document_id"] for p in pages}), pages_expected=len(expected_pages),
                   pages_successful=len(successful & expected_pages),
                   page_statuses=dict(Counter(p["status"] for p in pages)))
        images_path = source / "effective_pages.json"
        if not images_path.is_file():
            row["limitations"].append("missing_effective_image_identity")
        else:
            for page in read_json(images_path):
                if page["document_id"] not in ids:
                    continue
                page_key = page["document_id"], page["page_number"]
                actual_image = Path(page["run_image"])
                expected_image = page["run_image_sha256"]
                if file_hash(actual_image) != expected_image:
                    raise ValueError("Tatsächliches Laufbild wurde verändert")
                if page_key in shared_images and shared_images[page_key] != expected_image:
                    raise ValueError("Kandidaten wurden auf unterschiedlichen Seitenbildern ausgeführt")
                shared_images[page_key] = expected_image
        row["status"] = "complete" if successful == expected_pages and expected_pages else "incomplete"
        if not path.is_file():
            row["status"] = "missing"
        if pages and all(p["status"] == "unavailable" for p in pages):
            row["status"] = "unavailable"
        elif pages and all(p["status"] == "failed" for p in pages):
            row["status"] = "failed"
        for doc in documents:
            selected = [p for p in pages if p["document_id"] == doc["document_id"]]
            wall = [p.get("timings", {}).get("page_wall_seconds") for p in selected]
            complete_time = bool(wall) and all(v is not None for v in wall)
            timing_rows.append(dict(candidate=key, document_id=doc["document_id"], stratum=doc["stratum"],
                quality_flags=doc["quality_flags"], pages=len(selected),
                successful_pages=sum((p["document_id"], p["page_number"]) in successful for p in selected),
                page_wall_seconds=sum(wall) if complete_time else None,
                seconds_per_page=sum(wall) / len(wall) if complete_time else None,
                calls=sum(p["calls"] for p in selected) if selected and all("calls" in p for p in selected) else None,
                page_timings=[p.get("timings", {}) for p in selected]))
        row["source_method_wall_seconds"] = summary[candidate.method].get("actual_method_wall_seconds")
        resource_path = source / candidate.method / "resources.json"
        row["source_resources"] = read_json(resource_path) if resource_path.is_file() else None
        row["timing_note"] = "Page times exclude shared setup/load overhead; method wall/resources cover the full source run. "
        row["timing_note"] += "Cache/charged times remain in document_timings.csv. No cold/warm equivalence assumed."
        identities[key] = dict(source=str(source), manifest_sha256=file_hash(source / "manifest.json"),
            summary_sha256=file_hash(source / "summary.json"), config_sha256=file_hash(config_path),
            prompts_sha256=file_hash(prompts_path) if prompts_path.is_file() else None,
            extraction_sha256=file_hash(path) if path.is_file() else None,
            source_identity=read_json(source / "identity.json") if (source / "identity.json").is_file() else None,
            reused_comparison_hashes=source_artifacts.get(key))
        if candidate.role == "diagnostic":
            row["status"] = "diagnostic_only" if row["status"] == "complete" else row["status"]
            row["field_metric_status"] = "not_applicable"
            rows.append(row)
            continue
        qualities = {}
        for orientation, allow_swap in (("strict", False), ("reference_assisted", True)):
            config = benchmark.model_copy(deep=True)
            config.matching.compare_name_orientations = allow_swap
            _, scores = evaluate_run(source, reference_file, config, output, [candidate.method],
                output=output / "evaluations" / key / orientation,
                frozen_reference=(frozen, reference_hash), document_ids=ids, scientific_options=False)
            score = scores[candidate.method]
            qualities[orientation] = score
            for field, values in score.get("fields", {}).items():
                field_rows.append(dict(candidate=key, orientation=orientation, field=field, **values))
        # Keep the SAME pairs as the reference-assisted evaluation but score the source roles.
        # This uses the existing field counters; no alternate field formula is introduced.
        grouped, references = defaultdict(list), defaultdict(list)
        document_courses = {d["document_id"]: d["class_id"] for d in documents}
        for record in pages:
            page = PageResult.model_validate(record)
            grouped[document_courses[page.document_id]].extend(
                Prediction(page.document_id, page.page_number, index, person)
                for index, person in enumerate(page.participants))
        for person in frozen.people:
            references[person.class_id].append(person)
        paired_config = benchmark.matching.model_copy(update={"compare_name_orientations": True})
        original = aggregate([course_metrics(course, grouped[course], references[course], paired_config,
                            benchmark.reference, score_original_roles=True)[0] for course in sorted(courses)])
        qualities["original_roles"] = original
        for field, values in original["fields"].items():
            field_rows.append(dict(candidate=key, orientation="original_roles", field=field, **values))
        quality[key] = qualities
        strict, assisted = qualities["strict"], qualities["reference_assisted"]
        if strict["status"] != "evaluated":
            row["status"] = "not_applicable"
        o = original.get("overall", {})
        for name in ("exact_fields", "reference_fields", "predicted_fields", "incorrect_fields", "missing_fields",
                     "extra_fields", "field_coverage", "exact_precision", "exact_recall"):
            row[name] = o.get(name)
        row.update(original_exact_f1=o.get("exact_f1"), original_soft_f1=o.get("soft_f1"),
                   strict_exact_f1=strict.get("overall", {}).get("exact_f1"),
                   strict_soft_f1=strict.get("overall", {}).get("soft_f1"),
                   assisted_exact_f1=assisted.get("overall", {}).get("exact_f1"),
                   assisted_soft_f1=assisted.get("overall", {}).get("soft_f1"),
                   assisted_exact_fields=assisted.get("overall", {}).get("exact_fields"),
                   name_swaps=assisted.get("name_swapped_participants"))
        for name in ("reference_participants", "predicted_participants", "missing_participants", "extra_participants"):
            row[name] = strict.get(name)
        rows.append(row)
    matrix_rows, eligibility = matrix(policy)
    recommendation = recommend(policy, eligibility, rows, plan, scope)
    result = dict(version=1, scope=scope, plan_seal=plan["seal"], policy=plan["policy"],
                  sample={k: plan[k] for k in ("partitions", "pilot_lists", "pilot_groups", "pilot_strata",
                                             "missing_pilot_strata")},
                  documents_evaluated=len(ids), groups_evaluated=len({d["dependency_group"] for d in documents}),
                  strata_evaluated=dict(Counter(d["stratum"] for d in documents)),
                  matrix=eligibility, candidates=rows, metrics=quality, recommendation=recommendation,
                  identity=dict(sources=identities, reference_sha256=reference_hash,
                                implementation={p.name: file_hash(p) for p in Path(__file__).parent.glob("selection*.py")}))
    write_json(output / "selection.json", result)
    write_csv(output / "matrix.csv", matrix_rows)
    write_csv(output / "pilot.csv", [{k: v for k, v in r.items() if k != "source_resources"} for r in rows])
    write_csv(output / "field_scores.csv", field_rows, fields=None if field_rows else ["candidate", "orientation", "field"])
    write_csv(output / "document_timings.csv", timing_rows)
    from .selection_report import render

    render(output, result)
    return output


def run_selected(plan_path, output, candidates, *, scope="pilot"):
    plan, documents = load_plan(plan_path, scope)
    if not candidates or len(set(candidates)) != len(candidates) or set(candidates) - set(plan["profiles"]):
        raise ValueError("Kandidaten explizit und eindeutig wählen")
    if output.exists():
        raise ValueError("Neuen Ausgabeordner wählen")
    output.mkdir(parents=True)
    inputs = output / "inputs"
    for index, doc in enumerate(documents):
        target = inputs / str(index) / Path(doc["path"]).name
        target.parent.mkdir(parents=True)
        shutil.copyfile(doc["path"], target)
        if file_hash(target) != doc["document_id"]:
            raise ValueError("PDF beim Bereitstellen verändert")
    from .runner import run

    sources = {}
    for key in candidates:
        config = Config.model_validate(plan["profiles"][key])
        config.output_dir = str(output / "runs" / key)
        source, _ = run(config, inputs, offline=True)
        sources[key] = str(source.resolve())
        write_json(output / "sources.json", sources)
    return output / "sources.json"


def add_parser(commands):
    selection = commands.add_parser("selection", help="Evidenzmatrix, gruppierte Stichprobe und bestehender Pilotvergleich")
    subs = selection.add_subparsers(dest="selection_command", required=True)
    inv = subs.add_parser("inventory")
    inv.add_argument("--input", type=Path, required=True)
    inv.add_argument("--output", type=Path, required=True)
    sample = subs.add_parser("freeze")
    sample.add_argument("--inventory", type=Path, required=True)
    sample.add_argument("--policy", type=Path, default=Path("configs/selection.yaml"))
    sample.add_argument("--output", type=Path, required=True)
    for name in ("compare", "run"):
        sub = subs.add_parser(name)
        sub.add_argument("--plan", type=Path, required=True)
        sub.add_argument("--scope", choices=["development", "pilot"], default="pilot")
        sub.add_argument("--output", type=Path, required=True)
        if name == "run":
            sub.add_argument("--candidate", action="append", required=True)
        else:
            sub.add_argument("--source", action="append")
            sub.add_argument("--comparison", action="append")
            sub.add_argument("--sources", type=Path, help="sources.json eines selection run")
            sub.add_argument("--reference", type=Path)
            sub.add_argument("--benchmark-config", type=Path)


def execute(args):
    from .selection_sample import freeze, inventory

    if args.selection_command == "inventory":
        return inventory(args.input, args.output)
    if args.selection_command == "freeze":
        return freeze(args.inventory, args.policy, args.output)
    if args.selection_command == "run":
        return run_selected(args.plan, args.output, args.candidate, scope=args.scope)
    sources = bindings(args.source)
    if args.sources:
        saved = {key: Path(value) for key, value in json.loads(args.sources.read_text(encoding="utf-8")).items()}
        if set(saved) & set(sources):
            raise ValueError("Doppelte Quellen")
        sources.update(saved)
    return compare(args.plan, args.output, sources, bindings(args.comparison), scope=args.scope,
                   reference=args.reference, benchmark_path=args.benchmark_config)
