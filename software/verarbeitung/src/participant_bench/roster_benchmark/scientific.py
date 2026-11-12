"""Scientific views of frozen outputs using the existing course matcher/field counters."""

import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

from ..hybrid_evaluation import compare_fields, comparison_controls
from ..identifiers import user_id_rule
from ..io import digest, file_hash, read_json, read_jsonl, write_csv, write_json
from ..schema import PageResult
from .detail_report import read_csv
from .matching import Prediction, normalize
from .metrics import QUALITY_DEFINITIONS, aggregate, empty_counts
from .metrics import course_metrics as evaluate_course
from .references import saved_reference
from .scientific_efficiency import costs_per_1000, enrich_effort
from .scientific_metadata import course_metadata, load_metadata, template
from .scientific_stats import METRICS, cluster_bootstrap, pareto

VERSION = "scientific-evaluation-v2-dashboard"
MODES = ("original_roles", "best_fit_no_swap", "best_fit_swap", "conservative_no_swap", "conservative_swap")
PAIRS = (("vlm", "ocr_vlm"), ("docling", "docling_vlm"), ("ocr_llm", "paddle_llm"))


def variants(course, predictions, references, config):
    result = {}
    for mode in MODES:
        matching = config.matching.model_copy(
            update=dict(
                mode="conservative" if mode.startswith("conservative") else "best_fit",
                compare_name_orientations=mode not in ("best_fit_no_swap", "conservative_no_swap"),
            )
        )
        result[mode] = evaluate_course(
            course,
            predictions,
            references,
            matching,
            config.reference,
            score_original_roles=mode == "original_roles",
        )
    return result


def clusters(courses, metadata):
    counts = {}
    for course, score in courses.items():
        group = metadata[course]["dependency_group"]
        target = counts.setdefault(group, empty_counts())
        target.update({k: score["overall"][k] for k in target})
    return counts


def _sum_known(values):
    return sum(values) if values and all(v is not None for v in values) else None


def effort(source, method, pages, selected_ids):
    summary = read_json(source / "summary.json").get(method, {})
    manifest = read_json(source / "manifest.json")
    complete_scope = {r["sha256"] for r in manifest["inputs"] if r["kind"] == "pdf"} == selected_ids
    rows, cache, assists, assist_skips, cache_pages = [], [], [], 0, 0
    for page in pages:
        raw_path = source / method / f"raw-{page.page_id}.json"
        raw = read_json(raw_path) if raw_path.is_file() else {}
        timings = page.timings
        page_cache = [v for k, v in timings.items() if k.endswith("cache_hit")]
        assignment_cache = raw.get("assignment", {}).get("cache_hit")
        if assignment_cache is not None:
            page_cache.append(float(assignment_cache))
        cache.extend(page_cache)
        cache_pages += int(any(page_cache))
        assist = raw.get("docling_vlm_assist", {})
        if assist:
            assists.append(assist.get("vlm_calls", 0 if assist.get("vlm_called") is False else None))
            assist_skips += int(assist.get("status") == "skipped_complete_docling")
        rows.append(
            dict(
                document_id=page.document_id,
                page_number=page.page_number,
                status=page.status,
                parse_status=page.parse_status,
                page_wall_seconds=timings.get("page_wall_seconds"),
                calls=page.calls,
                timings=timings,
                assist_status=assist.get("status"),
                assist_seconds=timings.get("vlm_assist_seconds"),
                saved_response_generation_seconds=_sum_known(
                    [r.get("generation_seconds") for r in raw.get("responses", [])]
                ),
            )
        )
    measured = (
        "actual_method_wall_seconds",
        "full_pipeline_charged_seconds",
        "preprocessing_charged_seconds",
        "extraction_charged_seconds",
        "load_seconds",
        "load_attempt_wall_seconds",
        "warmup_seconds",
        "generation_calls",
        "model_calls",
        "ocr_inference_calls",
        "warmup_calls",
        "peak_ram_rss_bytes",
        "peak_gpu_allocated_bytes",
        "hybrid_ocr_cache_pages",
        "resume_reused_pages",
    )
    values = {key: summary.get(key) for key in measured}
    # A full-run duration is never proportionally allocated to a selected subset.
    values.update(
        scope_matches=complete_scope,
        page_wall_sum=_sum_known([r["page_wall_seconds"] for r in rows]),
        cache_pages=cache_pages,
        cache_observations=len(cache),
        cache_regime="cached_components"
        if any(cache)
        else "no_reported_cache"
        if cache or method == "vlm"
        else "unknown",
        assist_calls=_sum_known(assists),
        assist_skipped_pages=assist_skips,
        assist_seconds=_sum_known([r["assist_seconds"] for r in rows if r["assist_seconds"] is not None]),
    )
    values["source_scope_note"] = (
        "full_source_run" if complete_scope else "full_source_values_not_allocated_to_subset"
    )
    configuration=yaml.safe_load((source/"config.yaml").read_text(encoding="utf-8")) if (source/"config.yaml").is_file() else {}
    enrich_effort(values,rows,pages,summary,method,configuration)
    expected_count=sum(p.get("document_id") in selected_ids for p in manifest.get("pages",[]))
    values["costs"]=costs_per_1000(configuration,documents=len(selected_ids),pages=expected_count)
    return values, rows


def _source_comparison(output, source_run=None):
    """New and historical comparison snapshots use the same verification helper."""
    return saved_reference(output, source_run)


def _flatten_counts(score):
    return {key: score["overall"][key] for key in empty_counts()}


def analyze(
    output: Path,
    *,
    metadata=None,
    phase="all",
    resamples=2000,
    seed=42,
    minimum_groups=10,
    additional_reports=None,
    source_run=None,
    figures=True,
):
    if phase not in {"all", "development", "pilot", "test"}:
        raise ValueError("Unbekannte Evaluationsphase")
    if not 200 <= resamples <= 20000 or minimum_groups < 2:
        raise ValueError("Ungültige Bootstrap-Parameter")
    output = output.resolve()
    source, data, ref_hash, _, config = _source_comparison(output, source_run)
    original_manifest = read_json(source / "manifest.json")
    known = {p.class_id for p in data.people}
    annotations, metadata_identity, _ = load_metadata(original_manifest, known, metadata)
    scoped = read_csv(output / "documents.csv")
    selected_ids = {r["document_id"] for r in scoped if r.get("status") == "mapped"}
    courses = sorted({r["class_id"] for r in scoped if r.get("status") == "mapped"})
    course_info = {c: course_metadata(c, annotations, original_manifest) for c in courses}
    phases = {v["partition"] for v in course_info.values()}
    if phase != "all" and phases != {phase}:
        raise ValueError(
            "Vergleich enthält andere Phasen; analyze mit neuem --output auf die Phase begrenzen"
        )
    inference_eligible = bool(course_info) and all(
        v["grouping_reviewed"] and v["prior_use_reviewed"] for v in course_info.values()
    )
    inference_eligible = inference_eligible and len(phases) == 1 and "unknown" not in phases
    references = {c: [p for p in data.people if p.class_id == c] for c in courses}
    stored_metrics = read_json(output / "metrics.json")
    source_specs = {key: (source, key) for key in stored_metrics["methods"]}
    source_identities = {}
    baseline_reference = digest({c: [vars(p) for p in references[c]] for c in courses})
    for label, report in (additional_reports or {}).items():
        if label in source_specs or label not in {
            "docling",
            "docling_vlm",
            "ocr_llm",
            "paddle_llm",
            "vlm",
            "ocr_vlm",
            "ocr_rules",
        }:
            raise ValueError("Zusätzlichen Vergleich eindeutig mit vorhandener Kandidatenkennung angeben")
        other_source, other_data, _, _, other_config = saved_reference(Path(report))
        other_reference = {c: [vars(p) for p in other_data.people if p.class_id == c] for c in courses}
        if digest(other_reference) != baseline_reference or other_config.reference != config.reference:
            raise ValueError("Zusätzliche Vergleiche benötigen dieselbe eingefrorene Referenz")
        method = "docling" if label == "docling_vlm" else label
        if method not in read_json(Path(report) / "metrics.json")["methods"]:
            raise ValueError("Zusätzlicher Vergleich enthält den gewünschten Kandidaten nicht")
        extraction_config = yaml.safe_load((other_source / "config.yaml").read_text(encoding="utf-8"))
        if method == "docling" and bool(
            extraction_config.get("structures", {}).get("docling", {}).get("vlm_assist")
        ) != (label == "docling_vlm"):
            raise ValueError("Docling und Docling-VLM-Assist dürfen nicht verwechselt werden")
        present = {
            r["sha256"] for r in read_json(other_source / "manifest.json")["inputs"] if r["kind"] == "pdf"
        }
        if not selected_ids <= present:
            raise ValueError(
                "Zusätzlicher Kandidat wurde nicht auf denselben ausgewählten Dokumenten ausgeführt"
            )
        source_specs[label] = other_source, method
        source_identities[label] = dict(
            report=str(Path(report).resolve()), identity_sha256=file_hash(Path(report) / "identity.json")
        )
    overview, course_rows, field_rows, group_rows, effects, intervals, paired, transitions, ablations = (
        [] for _ in range(9)
    )
    field_summary, stratum_fields, ablation_strata = [], [], []
    distributions, quality, details, case_rows, efforts, page_rows, image_sets = {}, {}, {}, {}, {}, [], {}
    for candidate, (current_source, method) in source_specs.items():
        summary = read_json(current_source / "summary.json").get(method, {})
        path = current_source / method / "extractions.jsonl"
        pages = (
            [PageResult.model_validate(r) for r in read_jsonl(path) if r["document_id"] in selected_ids]
            if path.is_file()
            else []
        )
        keys = [(p.document_id, p.page_number) for p in pages]
        if len(set(keys)) != len(keys) or any(p.method_id != method for p in pages):
            raise ValueError("Doppelte Seiten oder abweichende Methode im Quelllauf")
        effort_data, timing_rows = effort(current_source, method, pages, selected_ids)
        efforts[candidate] = effort_data
        page_rows.extend(dict(candidate=candidate, **r) for r in timing_rows)
        effective = current_source / "effective_pages.json"
        images = {}
        if effective.is_file():
            for record in read_json(effective):
                if record["document_id"] in selected_ids:
                    expected = record.get("run_image_sha256")
                    image = (
                        Path(record["run_image"])
                        if record.get("run_image")
                        else current_source / "pages" / (record["page_id"] + ".png")
                    )
                    if expected and image.is_file() and file_hash(image) != expected:
                        raise ValueError("Gespeichertes Laufbild wurde verändert")
                    images[record["document_id"], record["page_number"]] = (
                        expected if image.is_file() else None
                    )
        image_sets[candidate] = images
        source_identities.setdefault(candidate, {})
        source_identities[candidate].update(
            source=str(current_source),
            method=method,
            manifest_sha256=file_hash(current_source / "manifest.json"),
            extraction_sha256=file_hash(path) if path.is_file() else None,
            config_sha256=file_hash(current_source / "config.yaml")
            if (current_source / "config.yaml").is_file()
            else None,
        )
        if summary.get("output_kind") == "ocr_text":
            overview.append(dict(candidate=candidate, status="not_applicable", reason="diagnostic_raw_text"))
            continue
        lookup = {d: annotations[d]["class_id"] for d in selected_ids}
        predictions = defaultdict(list)
        for page in pages:
            predictions[lookup[page.document_id]].extend(
                Prediction(page.document_id, page.page_number, i, p) for i, p in enumerate(page.participants)
            )
        quality[candidate], details[candidate], case_rows[candidate] = {}, {}, {}
        for mode in MODES:
            quality[candidate][mode], details[candidate][mode], case_rows[candidate][mode] = {}, [], []
        for course in courses:
            for mode, (score, cases, fields, _) in variants(
                course, predictions[course], references[course], config
            ).items():
                quality[candidate][mode][course] = score
                details[candidate][mode].extend(fields)
                case_rows[candidate][mode].extend(cases)
                course_rows.append(
                    dict(
                        candidate=candidate,
                        mode=mode,
                        **course_info[course],
                        **_flatten_counts(score),
                        exact_recall=score["overall"]["exact_recall"],
                        exact_f1=score["overall"]["exact_f1"],
                        soft_f1=score["overall"]["soft_f1"],
                        missing_participants=score["missing_participants"],
                        extra_participants=score["extra_participants"],
                    )
                )
                for field, counts in score["fields"].items():
                    field_rows.append(
                        dict(candidate=candidate, mode=mode, class_id=course, field=field, **counts)
                    )
        expected_pages = {
            (p["document_id"], p["page_number"])
            for p in original_manifest.get("pages", [])
            if p.get("document_id") in selected_ids and p.get("page_number") is not None
        }
        successful = {
            (p.document_id, p.page_number)
            for p in pages
            if p.status in ("success", "partial") and p.parse_status == "valid"
        }
        for mode, scores_by_course in quality[candidate].items():
            aggregate_score = aggregate(list(scores_by_course.values()))
            overall = aggregate_score["overall"]
            field_summary.extend(
                dict(candidate=candidate, mode=mode, field=field, **counts)
                for field, counts in aggregate_score["fields"].items()
            )
            status = (
                "not_assessable"
                if not courses
                else "missing_extractions"
                if not path.is_file()
                else "no_results"
                if not pages
                else "complete"
                if (successful == expected_pages and expected_pages)
                else "incomplete"
            )
            overview.append(
                dict(
                    candidate=candidate,
                    mode=mode,
                    status=status,
                    documents=len(selected_ids),
                    courses=len(courses),
                    pages=len(pages),
                    successful_pages=len(successful),
                    expected_pages=len(expected_pages),
                    page_statuses=dict(Counter(p.status for p in pages)),
                    **overall,
                    missing_participants=aggregate_score["missing_participants"],
                    extra_participants=aggregate_score["extra_participants"],
                    name_swapped_participants=aggregate_score["name_swapped_participants"],
                    participant_quality=aggregate_score["participant_quality"],
                )
            )
            grouped = clusters(scores_by_course, course_info)
            boot = cluster_bootstrap(
                grouped,
                seed=seed,
                resamples=resamples,
                minimum_groups=minimum_groups,
                eligible=inference_eligible and path.is_file() and bool(pages),
            )
            intervals.append(dict(candidate=candidate, mode=mode, **boot))
            for feature in (
                "stratum",
                "headerless",
                "variable_layout",
                "image_quality",
                "multipage_pdf",
                "partition",
            ):
                levels = sorted({info[feature] for info in course_info.values()})
                for level in levels:
                    selected = [s for c, s in scores_by_course.items() if course_info[c][feature] == level]
                    total = aggregate(selected)
                    stratum_fields.extend(
                        dict(
                            candidate=candidate,
                            mode=mode,
                            feature=feature,
                            level=level,
                            field=field,
                            **counts,
                        )
                        for field, counts in total["fields"].items()
                    )
                    group_rows.append(
                        dict(
                            candidate=candidate,
                            mode=mode,
                            feature=feature,
                            level=level,
                            courses=len(selected),
                            groups=len(
                                {
                                    course_info[c]["dependency_group"]
                                    for c in scores_by_course
                                    if course_info[c][feature] == level
                                }
                            ),
                            **total["overall"],
                        participant_quality=total["participant_quality"],
                            missing_participants=total["missing_participants"],
                            extra_participants=total["extra_participants"],
                        )
                    )
            if mode == "original_roles":
                distributions[candidate] = {}
                for metric in METRICS:
                    values = [
                        s["overall"][metric]
                        for s in scores_by_course.values()
                        if s["overall"][metric] is not None
                    ]
                    distributions[candidate][metric] = dict(
                        courses=len(values),
                        quantiles=dict(
                            zip(
                                ("min", "q25", "median", "q75", "max"),
                                map(float, np.quantile(values, [0, 0.25, 0.5, 0.75, 1])),
                                strict=True,
                            )
                        )
                        if values
                        else None,
                    )
        for before, after, explanation in (
            ("original_roles", "best_fit_swap", "Namens-Swap bei identischen Referenzpaaren"),
            ("best_fit_no_swap", "best_fit_swap", "Swap plus ggf. geänderte globale Paarung"),
            (
                "conservative_no_swap",
                "best_fit_no_swap",
                "Best-Fit statt konservativer Paarung, beide ohne Swap",
            ),
            ("conservative_swap", "best_fit_swap", "Best-Fit statt konservativer Paarung, beide mit Swap"),
        ):
            left, right = (clusters(quality[candidate][m], course_info) for m in (before, after))
            effects.append(
                dict(
                    candidate=candidate,
                    before=before,
                    after=after,
                    explanation=explanation,
                    extraction_changed=False,
                    **cluster_bootstrap(
                        left,
                        right,
                        seed=seed,
                        resamples=resamples,
                        minimum_groups=minimum_groups,
                        eligible=inference_eligible and path.is_file() and bool(pages),
                    ),
                )
            )
    primary = {r["candidate"]: r for r in overview if r.get("mode") == "original_roles"}
    for left, right in itertools.combinations(quality, 2):
        a, b = (clusters(quality[c]["original_roles"], course_info) for c in (left, right))
        paired.append(
            dict(
                baseline=left,
                comparison=right,
                **cluster_bootstrap(
                    a,
                    b,
                    seed=seed,
                    resamples=resamples,
                    minimum_groups=minimum_groups,
                    eligible=inference_eligible
                    and all(
                        primary[c]["status"] not in ("missing_extractions", "no_results")
                        for c in (left, right)
                    ),
                ),
            )
        )
    for row in intervals + effects + paired:
        names = [row["candidate"]] if "candidate" in row else [row["baseline"], row["comparison"]]
        missing = [
            name
            for name in names
            if primary[name]["status"] in ("missing_extractions", "no_results", "not_assessable")
        ]
        if missing:
            row["status"] = "not_assessable" if not courses else "missing_results"
            row["missing_candidates"] = missing
    for left, right in PAIRS:
        if left not in quality or right not in quality:
            ablations.append(
                dict(baseline=left, comparison=right, status="missing_comparison", causal_claim=False)
            )
            continue
        missing = [
            name
            for name in (left, right)
            if primary[name]["status"] in ("missing_extractions", "no_results", "not_assessable")
        ]
        if missing:
            ablations.append(
                dict(
                    baseline=left,
                    comparison=right,
                    status="missing_results",
                    missing_candidates=missing,
                    causal_claim=False,
                )
            )
            continue
        matching = config.matching.model_copy(update={"compare_name_orientations": False})
        analysis, changed = compare_fields(
            details[left]["original_roles"],
            details[right]["original_roles"],
            key_fields=("class_id", "reference_row"),
            normalize=lambda value, field: normalize(value, field, matching),
            source="frozen_course_reference_original_roles",
        )
        a_cases = {
            (r["class_id"], r["reference_row"]): r
            for r in case_rows[left]["original_roles"]
            if r.get("reference_row") is not None
        }
        b_cases = {
            (r["class_id"], r["reference_row"]): r
            for r in case_rows[right]["original_roles"]
            if r.get("reference_row") is not None
        }
        same_images = (
            bool(image_sets[left])
            and image_sets[left] == image_sets[right]
            and all(image_sets[left].values())
        )
        controls = (
            comparison_controls(source_specs[left][0])
            if (left, right) == ("vlm", "ocr_vlm") and source_specs[left][0] == source_specs[right][0]
            else {}
        )

        def delta(name):
            a, b = efforts[left].get(name), efforts[right].get(name)
            return b - a if isinstance(a, (float, int)) and isinstance(b, (float, int)) else None

        def matched(row):
            return row.get("status") == "matched"

        ablations.append(
            dict(
                baseline=left,
                comparison=right,
                **analysis,
                paired_courses=len(courses),
                same_document_set=True,
                same_actual_images=same_images,
                source_controls=controls,
                causal_claim=False,
                controls_note="Beschreibender Hinweisvergleich; Kontrolle ist keine allgemeine Kausalitätsgarantie"
                if controls.get("verified")
                else "Mehrere Pipelinekomponenten oder Versuchsbedingungen unterscheiden sich bzw. sind nicht belegt",
                formerly_unpaired_references_matched=sum(
                    not matched(a_cases[k]) and matched(b_cases[k]) for k in a_cases
                ),
                newly_unpaired_references=sum(
                    matched(a_cases[k]) and not matched(b_cases[k]) for k in a_cases
                ),
                extra_fields_delta=primary[right]["extra_fields"] - primary[left]["extra_fields"],
                method_wall_delta_seconds=delta("actual_method_wall_seconds")
                if all(efforts[c]["scope_matches"] for c in (left, right))
                else None,
                charged_delta_seconds=delta("full_pipeline_charged_seconds")
                if all(efforts[c]["scope_matches"] for c in (left, right))
                else None,
                generation_calls_delta=delta("generation_calls"),
                baseline_effort=efforts[left],
                comparison_effort=efforts[right],
            )
        )
        for row in changed:
            course = row["class_id"]
            for before, after in (
                ("vlm_value", "baseline_value"),
                ("ocr_vlm_value", "comparison_value"),
                ("vlm_exact", "baseline_exact"),
                ("ocr_vlm_exact", "comparison_exact"),
                ("vlm_distance", "baseline_distance"),
                ("ocr_vlm_distance", "comparison_distance"),
            ):
                row[after] = row.pop(before)
            transitions.append(
                dict(
                    baseline=left,
                    comparison=right,
                    stratum=course_info[course]["stratum"],
                    partition=course_info[course]["partition"],
                    **row,
                )
            )
        for stratum in sorted({course_info[c]["stratum"] for c in courses}):
            rows = [
                r
                for r in transitions
                if r["baseline"] == left and r["comparison"] == right and r["stratum"] == stratum
            ]
            counts = Counter(r["transition"] for r in rows)
            ablation_strata.append(
                dict(
                    baseline=left,
                    comparison=right,
                    stratum=stratum,
                    courses=sum(course_info[c]["stratum"] == stratum for c in courses),
                    fields=len(rows),
                    **{k: counts[k] for k in ("corrected", "regressed", "both_correct", "both_incorrect")},
                )
            )
    frontier = []
    for candidate, r in primary.items():
        e = efforts[candidate]
        frontier.append(
            dict(
                candidate=candidate,
                quality=r["exact_f1"],
                seconds=e["actual_method_wall_seconds"],
                cache_regime=e["cache_regime"],
                complete=r["status"] == "complete",
                comparable=e["scope_matches"],
            )
        )
    for regime in {r["cache_regime"] for r in frontier}:
        statuses = pareto([r for r in frontier if r["cache_regime"] == regime])
        for row in frontier:
            if row["candidate"] in statuses:
                row["pareto"] = statuses[row["candidate"]]
    folder = output / "scientific"
    folder.mkdir(exist_ok=True)
    if not (folder / "metadata_template.csv").exists():
        template(original_manifest, known, folder / "metadata_template.csv")
    primary_fields=[dict(method=candidate,**{k:"" if v is None else str(v) for k,v in row.items()})
                    for candidate in details for row in details[candidate]["original_roles"]]
    write_json(folder/"error_grading.json",dict(label="Originalrollen auf festen referenzgestützten Best-Fit-Paaren",
        document_ids=sorted(selected_ids),sources={c:source_identities[c] for c in quality},fields=primary_fields))
    from .error_report import render_errors

    render_errors(output)
    error_summary=read_json(output/"error_analysis/summary.json")
    dashboard_rows=[]
    for candidate,r in primary.items():
        e=efforts[candidate]
        dashboard_rows.append(dict(candidate=candidate,status=r["status"],reference_fields=r["reference_fields"],
            predicted_fields=r["predicted_fields"],exact_fields=r["exact_fields"],exact_recall=r["exact_recall"],
            exact_f1=r["exact_f1"],soft_f1=r["soft_f1"],field_coverage=r["field_coverage"],
            **r["participant_quality"],page_time_median=e["page_time"]["median"],page_times=e["page_time"]["n"],
            actual_calls=e["selected_actual_calls"],llm_calls=e["selected_llm_calls"],vlm_calls=e["selected_vlm_calls"],
            measured_eur_per_1000=e["costs"]["measured_eur_per_1000"],
            scenario_eur_per_1000=e["costs"]["scenario_eur_per_1000"],cache_regime=e["cache_regime"]))
    payload = dict(
        version=VERSION,
        phase=phase,
        observed_phases=sorted(phases),
        documents=len(selected_ids),
        courses=len(courses),
        groups=len({v["dependency_group"] for v in course_info.values()}),
        inference_eligible=inference_eligible,
        metadata=metadata_identity,
        course_metadata=course_info,
        overview=overview,
        strata=group_rows,
        field_summary=field_summary,
        intervals=intervals,
        paired=paired,
        matching_effects=effects,
        ablations=ablations,
        effort=efforts,
        pareto=frontier,
        distributions=distributions,
        ablation_strata=ablation_strata,
        errors=error_summary,
        dashboard=dashboard_rows,
        normalization_rule=user_id_rule(config.matching.ignore_leading_user_id_zeros),
        definitions=QUALITY_DEFINITIONS,
        bootstrap=dict(
            seed=seed,
            resamples=resamples,
            minimum_groups=minimum_groups,
            confidence=0.95,
            method="cluster_percentile",
        ),
        identity=dict(
            reference_sha256=ref_hash,
            reference_snapshot_sha256=file_hash(output / "reference_snapshot.json"),
            sources=source_identities,
            implementation={p.name: file_hash(p) for p in Path(__file__).parent.glob("scientific*.py")},
        ),
        limitations=[
            "reference_assisted_identity_even_without_swap",
            "course_reference_not_page_ground_truth",
            "no_handwriting_accuracy_from_unlocalized_roster",
            "metadata_unknown_is_not_inferred",
            "bootstrap_not_a_significance_proof",
            "group_review_does_not_prove_population_independence",
            "timing_and_resources_are_observed_not_controlled_benchmarks",
        ],
    )
    write_json(folder / "analysis.json", payload)
    for name, rows, columns in (
        ("courses", course_rows, ["candidate", "mode", "class_id"]),
        ("fields", field_rows, ["candidate", "mode", "class_id", "field"]),
        ("dashboard",dashboard_rows,["candidate","exact_recall","exact_f1"]),
        ("metric_definitions",QUALITY_DEFINITIONS,["key","label","numerator","denominator","unit","direction"]),
        ("participant_scores",[dict(candidate=c,mode=mode,class_id=course,**s["participant_quality"])
            for c,by_mode in quality.items() for mode,by_course in by_mode.items() for course,s in by_course.items()],
            ["candidate","mode","class_id"]),
        ("participant_cases",[dict(candidate=c,mode=mode,**r) for c,by_mode in case_rows.items()
            for mode,rows in by_mode.items() for r in rows],["candidate","mode","class_id","reference_row"]),
        ("document_calls",[dict(candidate=c,**r) for c,e in efforts.items() for r in e["document_calls"]],
            ["candidate","document_id","actual_calls"]),
        ("costs",[dict(candidate=c,**e["costs"]) for c,e in efforts.items()],["candidate","status"]),
        ("strata_fields", stratum_fields, ["candidate", "mode", "feature", "level", "field"]),
        ("strata", group_rows, ["candidate", "mode", "feature", "level"]),
        ("matching_effects", effects, ["candidate", "before", "after"]),
        ("paired", paired, ["baseline", "comparison"]),
        ("ablations", ablations, ["baseline", "comparison", "status"]),
        ("ablation_strata", ablation_strata, ["baseline", "comparison", "stratum"]),
        ("transitions", transitions, ["baseline", "comparison", "class_id", "field", "transition"]),
        ("page_timings", page_rows, ["candidate", "document_id", "page_number"]),
        ("pareto", frontier, ["candidate", "quality", "seconds", "pareto"]),
    ):
        csv_rows = [
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                for k, v in r.items()
            }
            for r in rows
        ]
        write_csv(folder / (name + ".csv"), csv_rows, fields=None if rows else columns)
    flat_intervals = [
        dict(
            candidate=r["candidate"],
            mode=r["mode"],
            status=r["status"],
            groups=r["groups"],
            metric=metric,
            estimate=r["estimates"][metric],
            **r["intervals"][metric],
        )
        for r in intervals
        for metric in METRICS
    ]
    write_csv(
        folder / "intervals.csv",
        flat_intervals,
        fields=None if flat_intervals else ["candidate", "mode", "metric"],
    )
    from .scientific_report import render

    render(output, payload, figures=figures)
    return payload


def reanalyze(report, output, *, metadata=None, phase="all", source_run=None, **options):
    """New regular comparison directory; original report, outputs and references stay untouched."""
    if output.exists():
        raise ValueError("Neuen, noch nicht vorhandenen Ergebnisordner angeben")
    source, data, ref_hash, reference, config = saved_reference(report, source_run)
    manifest = read_json(source / "manifest.json")
    documents, _, _ = load_metadata(manifest, {p.class_id for p in data.people}, metadata)
    scoped = {r["document_id"] for r in read_csv(report / "documents.csv") if r.get("status") == "mapped"}
    selected = {d for d in scoped if phase == "all" or documents[d]["partition"] == phase}
    if not selected:
        raise ValueError("Keine Dokumente in der gewählten Phase")
    from .evaluation import evaluate_run

    evaluate_run(
        source,
        reference,
        config,
        output.parent,
        methods=list(read_json(report / "metrics.json")["methods"]),
        output=output,
        frozen_reference=(data, ref_hash),
        document_ids=selected,
        scientific_options=False,
    )
    return analyze(output, metadata=metadata, phase=phase, source_run=source, **options)


def metadata_template(report, output, source_run=None):
    source, data, *_ = saved_reference(report, source_run)
    return template(read_json(source / "manifest.json"), {p.class_id for p in data.people}, output)
