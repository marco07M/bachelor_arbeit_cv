"""Exact and fractional field credit. Missing fields and extra predictions retain explicit denominators."""

from collections import Counter

from ..evaluation import edits
from ..output_order import ordered_rows
from ..person_roles import UNCONFIRMED_ROLE
from .matching import FIELDS, align, normalize, similarity, values


def divide(numerator, denominator):
    return numerator / denominator if denominator else None


def scores(count):
    reference, predicted = count["reference_fields"], count["predicted_fields"]
    total = reference + predicted
    return dict(count, exact_reference_accuracy=divide(count["exact_fields"], reference),
                raw_exact_reference_accuracy=divide(count["raw_exact_fields"], reference),
                exact_f1=divide(2 * count["exact_fields"], total) if reference else None,
                soft_precision=divide(count["similarity_credit"], predicted),
                soft_recall=divide(count["similarity_credit"], reference),
                soft_f1=divide(2 * count["similarity_credit"], total) if reference else None)


def empty_counts():
    return Counter(reference_fields=0, predicted_fields=0, exact_fields=0, raw_exact_fields=0,
                   similarity_credit=0.0, excluded_reference_fields=0, excluded_masked_predictions=0)


def course_metrics(class_id, predictions, references, config, reference_config):
    if any(person.class_id != class_id for person in references):
        raise ValueError("Referenzzeilen verschiedener Schulungen dürfen nicht gemeinsam zugeordnet werden")
    matches, issues, candidates = align(predictions, references, config, reference_config)
    by_reference = {match.reference: match for match in matches}
    fields = {field: empty_counts() for field in FIELDS}
    details, rows = [], []
    full_rows = 0
    comparable = {field for field in FIELDS if any(getattr(person, field).strip() and
                   (field != "user_id" or reference_config.usable_id(person.user_id)) for person in references)}
    for j, reference in enumerate(references):
        match = by_reference.get(j)
        prediction = predictions[match.prediction] if match else None
        role_review = prediction is not None and UNCONFIRMED_ROLE in prediction.person.review_notes
        review_reasons = list(match.review_reasons) if match else []
        if role_review:
            review_reasons.append("role_unconfirmed")
        actual = values(prediction, config) if prediction else dict.fromkeys(FIELDS)
        row = dict(class_id=class_id, reference_row=reference.row_number,
                   document_id=prediction.document_id if prediction else None,
                   page_number=prediction.page_number if prediction else None,
                   output_index=prediction.index if prediction else None,
                   status="matched" if match else "missing", matching_source=match.source if match else None,
                   identity_similarity=match.similarity if match else None,
                   alternative_gap=match.alternative_gap if match else None,
                   matching_mode=config.mode,
                   matching_review_reasons=" | ".join(review_reasons))
        evaluated, correct = 0, 0
        review = not match or match.similarity < 1.0 or bool(review_reasons)
        for field, model_field in FIELDS.items():
            expected, observed = getattr(reference, field), actual[field]
            count = fields[field]
            eligible = bool(expected.strip()) and (field != "user_id" or reference_config.usable_id(expected))
            reason = None if eligible else "reference_missing_or_masked"
            if eligible and field == "user_id" and observed and not reference_config.usable_id(observed):
                eligible, reason = False, "prediction_explicitly_masked_or_placeholder_confirm_in_pdf"
                count["excluded_masked_predictions"] += 1
                review = True
            if not eligible:
                count["excluded_reference_fields"] += int(reason == "reference_missing_or_masked")
            left, right = normalize(expected, field, config), normalize(observed, field, config)
            exact = bool(observed is not None and left == right) if eligible else None
            raw_exact = observed == expected if eligible else None
            credit = similarity(left, right) if eligible and observed is not None else 0.0
            if eligible:
                count.update(reference_fields=1, predicted_fields=int(bool(right)),
                             exact_fields=int(exact), raw_exact_fields=int(raw_exact), similarity_credit=credit)
                evaluated += 1
                correct += int(exact)
                review = review or not exact or (prediction is not None and
                                                 getattr(prediction.person, model_field).state == "uncertain")
            details.append(dict(row, field=field, reference_value=expected, prediction_value=observed,
                                prediction_state=getattr(prediction.person, model_field).state if prediction else "missing",
                                assessable=eligible, exclusion_reason=reason, exact=exact, raw_exact=raw_exact,
                                levenshtein_distance=edits(left, right) if eligible else None,
                                similarity=credit if eligible else None,
                                review_required=(match is None or bool(review_reasons) or reason == "prediction_explicitly_masked_or_placeholder_confirm_in_pdf"
                                                 or bool(eligible and (not exact or (prediction is not None and
                                                         getattr(prediction.person, model_field).state == "uncertain")))),
                                identity_alignment_used_reference=True))
        row["fully_exact"] = bool(match and evaluated and evaluated == correct)
        row["review_required"] = bool(review)
        full_rows += int(row["fully_exact"])
        rows.append(row)
    for i, status in issues.items():
        prediction = predictions[i]
        row = dict(class_id=class_id, reference_row=None, document_id=prediction.document_id,
                   page_number=prediction.page_number, output_index=prediction.index, status=status,
                   matching_source=None, identity_similarity=None, alternative_gap=None, fully_exact=False,
                   matching_mode=config.mode, matching_review_reasons=status)
        row["review_required"] = True
        rows.append(row)
        for field, observed in values(prediction, config).items():
            eligible = field in comparable and bool(observed) and (
                field != "user_id" or reference_config.usable_id(observed))
            if eligible:
                fields[field]["predicted_fields"] += 1
            details.append(dict(row, field=field, reference_value=None, prediction_value=observed,
                                prediction_state=getattr(prediction.person, FIELDS[field]).state,
                                assessable=eligible, exclusion_reason=None if eligible else "not_comparable_extra_field",
                                exact=False if eligible else None, raw_exact=False if eligible else None,
                                levenshtein_distance=None, similarity=0.0 if eligible else None,
                                identity_alignment_used_reference=True))
    total = empty_counts()
    for count in fields.values():
        total.update(count)
    result = dict(class_id=class_id, reference_participants=len(references), predicted_participants=len(predictions),
                  matching_mode=config.mode,
                  assigned_participants=len(matches), missing_participants=len(references) - len(matches),
                  extra_participants=len(issues), fully_exact_participants=full_rows,
                  ambiguous_participants=sum(value == "ambiguous" for value in issues.values()),
                  identity_conflicts=sum(value == "identity_conflict" for value in issues.values()),
                  duplicate_predictions=sum(value == "duplicate_prediction" for value in issues.values()),
                  low_similarity_assignments=sum("low_similarity" in match.review_reasons for match in matches),
                  ambiguous_assignments=sum("ambiguous" in match.review_reasons for match in matches),
                  conflicting_assignments=sum("identity_conflict" in match.review_reasons for match in matches),
                  duplicate_assignments=sum("duplicate_prediction" in match.review_reasons for match in matches),
                  review_rows=sum(row["review_required"] for row in rows),
                  fields={field: scores(count) for field, count in fields.items()}, overall=scores(total),
                  fully_exact_participant_recall=divide(full_rows, len(references)))
    result["score_percent"] = 100 * result["overall"]["soft_f1"] if result["overall"]["soft_f1"] is not None else None
    documents = {doc: i for i, doc in enumerate(dict.fromkeys(p.document_id for p in predictions))}
    return result, ordered_rows(rows, documents), ordered_rows(details, documents), candidates


def aggregate(courses):
    fields = {field: empty_counts() for field in FIELDS}
    result = {key: sum(course[key] for course in courses) for key in (
        "reference_participants", "predicted_participants", "assigned_participants", "missing_participants",
        "extra_participants", "fully_exact_participants", "ambiguous_participants", "identity_conflicts",
        "duplicate_predictions", "review_rows", "low_similarity_assignments", "ambiguous_assignments",
        "conflicting_assignments", "duplicate_assignments")}
    for course in courses:
        for field in FIELDS:
            fields[field].update({key: course["fields"][field][key] for key in empty_counts()})
    total = empty_counts()
    for count in fields.values():
        total.update(count)
    result.update(fields={field: scores(count) for field, count in fields.items()}, overall=scores(total),
                  matching_mode=courses[0]["matching_mode"] if courses else "conservative",
                  courses=len(courses), fully_exact_participant_recall=divide(result["fully_exact_participants"],
                                                                           result["reference_participants"]))
    result["score_percent"] = 100 * result["overall"]["soft_f1"] if result["overall"]["soft_f1"] is not None else None
    return result
