"""Exact and fractional field credit. Missing fields and extra predictions retain explicit denominators."""

from collections import Counter

from ..evaluation import edits
from ..output_order import ordered_rows
from ..person_roles import UNCONFIRMED_ROLE
from ..reference_states import reference_state
from .matching import FIELDS, align, normalize, similarity, values


def divide(numerator, denominator):
    return numerator / denominator if denominator else None


def scores(count):
    reference, predicted = count["reference_fields"], count["predicted_fields"]
    total = reference + predicted
    return dict(
        count,
        exact_reference_accuracy=divide(count["exact_fields"], reference),
        exact_precision=divide(count["exact_fields"], predicted),
        exact_recall=divide(count["exact_fields"], reference),
        tp=count["exact_fields"],
        fp=predicted - count["exact_fields"],
        fn=reference - count["exact_fields"],
        field_coverage=divide(reference - count["missing_fields"], reference),
        missing_rate=divide(count["missing_fields"], reference),
        incorrect_rate=divide(count["incorrect_fields"], reference),
        raw_exact_reference_accuracy=divide(count["raw_exact_fields"], reference),
        exact_f1=divide(2 * count["exact_fields"], total) if reference else None,
        soft_precision=divide(count["similarity_credit"], predicted),
        soft_recall=divide(count["similarity_credit"], reference),
        soft_f1=divide(2 * count["similarity_credit"], total) if reference else None,
    )


def empty_counts():
    return Counter(
        reference_fields=0,
        predicted_fields=0,
        exact_fields=0,
        raw_exact_fields=0,
        similarity_credit=0.0,
        excluded_reference_fields=0,
        excluded_masked_predictions=0,
        incorrect_fields=0,
        missing_fields=0,
        extra_fields=0,
        invalid_prediction_fields=0,
        reference_empty_fields=0,
        correct_empty_fields=0,
        hallucinated_empty_fields=0,
    )


PARTICIPANT_COUNTERS = (
    "reference_participants",
    "complete_reference_participants",
    "partial_reference_participants",
    "unassessable_reference_participants",
    "fully_correct_complete_participants",
    "fully_correct_partial_participants",
    "identity_assessable_participants",
    "identity_unassessable_participants",
    "identity_exact_participants",
)

QUALITY_DEFINITIONS = [
    dict(
        key="exact_recall",
        label="Exakter Feld-Recall",
        numerator="exakte normalisierte Referenzfeldtreffer E",
        denominator="bewertbare nichtleere Referenzfelder R",
        formula="E/R",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="exact_f1",
        label="Exakter Feld-F1",
        numerator="2E",
        denominator="R+P (bewertete Referenz- und Ausgabefelder)",
        formula="2E/(R+P)",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="complete_participant_accuracy",
        label="Vollständige Teilnehmer",
        numerator="vier bestimmbare Pflichtfelder sämtlich korrekt",
        denominator="Referenzpersonen mit vier bestimmbaren Pflichtfeldern (read/empty)",
        formula="C_complete/N_complete",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="partial_participant_accuracy",
        label="Korrekte Teilreferenzen (separat)",
        numerator="alle bestimmbaren Felder der Teilreferenz korrekt",
        denominator="Referenzpersonen mit 1–3 bestimmbaren Pflichtfeldern",
        formula="C_partial/N_partial",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="participant_recall",
        label="Teilnehmer-Recall (striktes Referenzkriterium)",
        numerator="eindeutiger Referenzanker und alle bestimmbaren Identitätsfelder exakt",
        denominator="Referenzpersonen mit eindeutiger lesbarer ID oder eindeutiger lesbarer vollständiger Namenskombination innerhalb der Schulung",
        formula="I_exact/I_assessable",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="field_coverage",
        label="Field Coverage",
        numerator="R minus fehlende/ungültige Werte bei bewertbaren Referenzfeldern",
        denominator="R",
        formula="(R-missing_fields)/R",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="missing_rate",
        label="Anteil fehlender Felder",
        numerator="fehlende/ungültige Werte für bewertbare Referenzfelder M",
        denominator="R",
        formula="M/R",
        unit="fraction",
        direction="lower",
    ),
    dict(
        key="incorrect_rate",
        label="Anteil falscher Felder",
        numerator="vorhandene, nicht exakte Werte für bewertbare Referenzfelder W",
        denominator="R",
        formula="W/R",
        unit="fraction",
        direction="lower",
    ),
    dict(
        key="soft_f1",
        label="Levenshtein-Feld-F1 (separat)",
        numerator="2S (summierte Ähnlichkeitsgutschrift)",
        denominator="R+P",
        formula="2S/(R+P)",
        unit="fraction",
        direction="higher",
    ),
    dict(
        key="page_time_median",
        label="Median der beobachteten Seitenzeit",
        numerator="vorhandene page_wall_seconds",
        denominator="Anzahl beobachteter Seitenzeiten; keine anteiligen Ladezeiten",
        formula="median(page_wall_seconds)",
        unit="seconds",
        direction="lower",
    ),
    dict(
        key="actual_calls",
        label="Tatsächliche gespeicherte Modellaufrufe",
        numerator="PageResult.calls mit konsistenten Quellzählern",
        denominator="Seite/PDF gemäß Export; Warm-up separat",
        formula="sum(actual_calls)",
        unit="calls",
        direction="lower",
    ),
    dict(
        key="costs_1000",
        label="Kosten pro 1.000 Dokumente",
        numerator="belegte Geldmessungen oder getrennte Profilannahmen",
        denominator="1.000 PDFs; Szenario umgerechnet mit beobachteten Seiten/PDF",
        formula="cost_per_page * pages_per_pdf * 1000",
        unit="EUR/1000 PDFs",
        direction="lower",
    ),
]


def participant_scores(counts):
    return dict(
        counts,
        complete_participant_accuracy=divide(
            counts["fully_correct_complete_participants"], counts["complete_reference_participants"]
        ),
        partial_participant_accuracy=divide(
            counts["fully_correct_partial_participants"], counts["partial_reference_participants"]
        ),
        participant_recall=divide(
            counts["identity_exact_participants"], counts["identity_assessable_participants"]
        ),
    )


def participant_quality(references, rows, details, config, reference_config):
    """Additional strict dimensions; never equate a best-fit pair with identity correctness.

    The selected alignment is retained. Every assessable identity field must be
    exact, with a unique readable ID or unique readable full-name pair as an anchor.
    Reference-empty fields require an explicitly empty output, as in existing counts.
    """
    indexed = {(r["reference_row"], r["field"]): r for r in details if r["reference_row"] is not None}
    ids, names = Counter(), Counter()
    for person in references:
        if reference_state(person, "user_id", reference_config) == "read" and reference_config.usable_id(
            person.user_id
        ):
            ids[normalize(person.user_id, "user_id", config)] += 1
        if all(reference_state(person, f, reference_config) == "read" for f in ("first_name", "last_name")):
            names[tuple(normalize(getattr(person, f), f, config) for f in ("first_name", "last_name"))] += 1
    count = Counter(dict.fromkeys(PARTICIPANT_COUNTERS, 0))
    for row in rows:
        if row["reference_row"] is None:
            continue
        fields = {f: indexed[row["reference_row"], f] for f in FIELDS}
        known = {f for f, r in fields.items() if r["reference_state"] in ("read", "empty")}

        def correct(field):
            r = fields[field]
            return (
                r["exact"] is True
                if r["reference_state"] == "read"
                else (
                    r["reference_state"] == "empty"
                    and r["prediction_value"] is not None
                    and not r["normalized_prediction"]
                )
            )

        complete = len(known) == len(FIELDS)
        all_correct = bool(known) and row["status"] == "matched" and all(correct(f) for f in known)
        identity_fields = known & {"first_name", "last_name", "user_id"}
        id_value = fields["user_id"]["normalized_reference"]
        name_value = tuple(fields[f]["normalized_reference"] for f in ("first_name", "last_name"))
        basis = (
            "unique_id"
            if fields["user_id"]["reference_state"] == "read" and ids[id_value] == 1
            else (
                "unique_full_name"
                if all(fields[f]["reference_state"] == "read" for f in ("first_name", "last_name"))
                and names[name_value] == 1
                else None
            )
        )
        identity_exact = bool(
            basis and row["status"] == "matched" and all(correct(f) for f in identity_fields)
        )
        row.update(
            reference_completeness="complete" if complete else "partial" if known else "unassessable",
            assessable_required_fields=len(known),
            fully_correct_required=bool(complete and all_correct),
            fully_correct_assessed_fields=all_correct,
            identity_basis=basis,
            identity_assessable=bool(basis),
            identity_exact=identity_exact,
            identity_is_reference_based=True,
        )
        count.update(
            reference_participants=1,
            complete_reference_participants=int(complete),
            partial_reference_participants=int(bool(known) and not complete),
            unassessable_reference_participants=int(not known),
            fully_correct_complete_participants=int(complete and all_correct),
            fully_correct_partial_participants=int(bool(known) and not complete and all_correct),
            identity_assessable_participants=int(bool(basis)),
            identity_unassessable_participants=int(not basis),
            identity_exact_participants=int(identity_exact),
        )
    return participant_scores(count)


def course_metrics(
    class_id, predictions, references, config, reference_config, *, score_original_roles=False
):
    """Optionally score original name roles on the unchanged reference-assisted alignment."""
    if any(person.class_id != class_id for person in references):
        raise ValueError("Referenzzeilen verschiedener Schulungen dürfen nicht gemeinsam zugeordnet werden")
    matches, issues, candidates = align(predictions, references, config, reference_config)
    by_reference = {match.reference: match for match in matches}
    fields = {field: empty_counts() for field in FIELDS}
    details, rows = [], []
    full_rows = 0
    comparable = {
        field
        for field in FIELDS
        if any(reference_state(person, field, reference_config) in ("read", "empty") for person in references)
    }
    for j, reference in enumerate(references):
        match = by_reference.get(j)
        prediction = predictions[match.prediction] if match else None
        role_review = prediction is not None and UNCONFIRMED_ROLE in prediction.person.review_notes
        review_reasons = list(match.review_reasons) if match else []
        if role_review:
            review_reasons.append("role_unconfirmed")
        actual = values(prediction, config) if prediction else dict.fromkeys(FIELDS)
        original = {
            field: getattr(prediction.person, model_field).value if prediction else None
            for field, model_field in FIELDS.items()
        }
        swapped = bool(match and match.name_swapped and not score_original_roles)
        if swapped:
            actual["first_name"], actual["last_name"] = actual["last_name"], actual["first_name"]
        row = dict(
            class_id=class_id,
            reference_row=reference.row_number,
            document_id=prediction.document_id if prediction else None,
            page_number=prediction.page_number if prediction else None,
            output_index=prediction.index if prediction else None,
            status="matched" if match else "missing",
            matching_source=match.source if match else None,
            identity_similarity=match.similarity if match else None,
            alternative_gap=match.alternative_gap if match else None,
            matching_mode=config.mode,
            name_swapped=swapped,
            matching_review_reasons=" | ".join(review_reasons),
        )
        evaluated, correct = 0, 0
        review = not match or match.similarity < 1.0 or bool(review_reasons)
        for field, model_field in FIELDS.items():
            expected, observed = getattr(reference, field), actual[field]
            count = fields[field]
            state = reference_state(reference, field, reference_config)
            eligible = state == "read"
            reason = (
                None if eligible else "reference_empty" if state == "empty" else "reference_missing_or_masked"
            )
            invalid = bool(
                eligible and field == "user_id" and observed and not reference_config.usable_id(observed)
            )
            if invalid:
                reason = "invalid_prediction_placeholder"
                count["invalid_prediction_fields"] += 1
            if not eligible:
                count["excluded_reference_fields"] += int(reason == "reference_missing_or_masked")
            left, right = normalize(expected, field, config), normalize(observed, field, config)
            available = bool(right) and not invalid
            exact = bool(available and left == right) if eligible else None
            raw_exact = bool(available and observed == expected) if eligible else None
            credit = similarity(left, right) if eligible and available else 0.0
            source_field = (
                {"first_name": "last_name", "last_name": "first_name"}.get(field, field) if swapped else field
            )
            prediction_state = (
                getattr(prediction.person, FIELDS[source_field]).state if prediction else "missing"
            )
            if eligible:
                count.update(
                    reference_fields=1,
                    predicted_fields=int(bool(right)),
                    exact_fields=int(exact),
                    raw_exact_fields=int(raw_exact),
                    similarity_credit=credit,
                    missing_fields=int(not available),
                    incorrect_fields=int(available and not exact),
                )
                evaluated += 1
                correct += int(exact)
                review = review or not exact or prediction_state == "uncertain"
            elif state == "empty":
                count.update(
                    reference_empty_fields=1,
                    correct_empty_fields=int(observed is not None and not right),
                    hallucinated_empty_fields=int(bool(right)),
                    predicted_fields=int(bool(right)),
                    extra_fields=int(bool(right)),
                )
            details.append(
                dict(
                    row,
                    field=field,
                    reference_value=expected,
                    prediction_value=observed,
                    original_prediction_value=original[field],
                    reference_state=state,
                    normalized_reference=left,
                    normalized_prediction=right,
                    prediction_state=prediction_state,
                    assessable=eligible,
                    exclusion_reason=reason,
                    exact=exact,
                    raw_exact=raw_exact,
                    reference_contribution=int(eligible),
                    prediction_contribution=int(bool(right) and (eligible or state == "empty")),
                    levenshtein_distance=edits(left, right) if eligible else None,
                    similarity=credit if eligible else None,
                    review_required=(
                        match is None
                        or bool(review_reasons)
                        or invalid
                        or bool(eligible and (not exact or prediction_state == "uncertain"))
                    ),
                    identity_alignment_used_reference=True,
                )
            )
        row["fully_exact"] = bool(match and evaluated and evaluated == correct)
        row["review_required"] = bool(review)
        full_rows += int(row["fully_exact"])
        rows.append(row)
    for i, status in issues.items():
        prediction = predictions[i]
        row = dict(
            class_id=class_id,
            reference_row=None,
            document_id=prediction.document_id,
            page_number=prediction.page_number,
            output_index=prediction.index,
            status=status,
            matching_source=None,
            identity_similarity=None,
            alternative_gap=None,
            fully_exact=False,
            matching_mode=config.mode,
            matching_review_reasons=status,
        )
        row["review_required"] = True
        rows.append(row)
        for field, observed in values(prediction, config).items():
            eligible = field in comparable and bool(observed)
            if eligible:
                fields[field]["predicted_fields"] += 1
                fields[field]["extra_fields"] += 1
            details.append(
                dict(
                    row,
                    field=field,
                    reference_value=None,
                    prediction_value=observed,
                    prediction_state=getattr(prediction.person, FIELDS[field]).state,
                    assessable=eligible,
                    exclusion_reason=None if eligible else "not_comparable_extra_field",
                    reference_contribution=0,
                    prediction_contribution=int(eligible),
                    exact=False if eligible else None,
                    raw_exact=False if eligible else None,
                    levenshtein_distance=None,
                    similarity=0.0 if eligible else None,
                    identity_alignment_used_reference=True,
                )
            )
    total = empty_counts()
    for count in fields.values():
        total.update(count)
    result = dict(
        class_id=class_id,
        reference_participants=len(references),
        predicted_participants=len(predictions),
        matching_mode=config.mode,
        name_swapped_participants=sum(match.name_swapped and not score_original_roles for match in matches),
        assigned_participants=len(matches),
        missing_participants=len(references) - len(matches),
        extra_participants=len(issues),
        fully_exact_participants=full_rows,
        ambiguous_participants=sum(value == "ambiguous" for value in issues.values()),
        identity_conflicts=sum(value == "identity_conflict" for value in issues.values()),
        duplicate_predictions=sum(value == "duplicate_prediction" for value in issues.values()),
        low_similarity_assignments=sum("low_similarity" in match.review_reasons for match in matches),
        ambiguous_assignments=sum("ambiguous" in match.review_reasons for match in matches),
        conflicting_assignments=sum("identity_conflict" in match.review_reasons for match in matches),
        duplicate_assignments=sum("duplicate_prediction" in match.review_reasons for match in matches),
        review_rows=sum(row["review_required"] for row in rows),
        fields={field: scores(count) for field, count in fields.items()},
        overall=scores(total),
        fully_exact_participant_recall=divide(full_rows, len(references)),
    )
    result["score_percent"] = (
        100 * result["overall"]["soft_f1"] if result["overall"]["soft_f1"] is not None else None
    )
    result["participant_quality"] = participant_quality(references, rows, details, config, reference_config)
    documents = {doc: i for i, doc in enumerate(dict.fromkeys(p.document_id for p in predictions))}
    return result, ordered_rows(rows, documents), ordered_rows(details, documents), candidates


def aggregate(courses):
    fields = {field: empty_counts() for field in FIELDS}
    result = {
        key: sum(course[key] for course in courses)
        for key in (
            "reference_participants",
            "predicted_participants",
            "assigned_participants",
            "missing_participants",
            "extra_participants",
            "fully_exact_participants",
            "ambiguous_participants",
            "identity_conflicts",
            "duplicate_predictions",
            "review_rows",
            "low_similarity_assignments",
            "ambiguous_assignments",
            "conflicting_assignments",
            "duplicate_assignments",
            "name_swapped_participants",
        )
    }
    for course in courses:
        for field in FIELDS:
            fields[field].update({key: course["fields"][field][key] for key in empty_counts()})
    total = empty_counts()
    for count in fields.values():
        total.update(count)
    result.update(
        fields={field: scores(count) for field, count in fields.items()},
        overall=scores(total),
        matching_mode=courses[0]["matching_mode"] if courses else "conservative",
        courses=len(courses),
        fully_exact_participant_recall=divide(
            result["fully_exact_participants"], result["reference_participants"]
        ),
    )
    result["score_percent"] = (
        100 * result["overall"]["soft_f1"] if result["overall"]["soft_f1"] is not None else None
    )
    quality = Counter(dict.fromkeys(PARTICIPANT_COUNTERS, 0))
    available = all("participant_quality" in c for c in courses)
    if available:
        for course in courses:
            quality.update({key: course["participant_quality"][key] for key in PARTICIPANT_COUNTERS})
    result["participant_quality"] = (
        participant_scores(quality) if available else dict(status="unavailable_legacy_counts")
    )
    return result
