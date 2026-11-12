"""Bounded OCR evidence for right-angle orientation, independent of target fields/GT."""

import math

VERSION = "orientation-v1-osd-ocr-comparison"
# Keep a normal 220-DPI A4 page at its original resolution. Probe-only limit;
# extraction always receives the full-resolution, rotated original pixels.
MAX_SIDE = 2600
MIN_WORD_CONFIDENCE = 50
MIN_WORDS = 5
MIN_LETTERS = 25
MIN_SCORE_GAP = 15
MIN_SCORE_RATIO = 1.5


def text_evidence(data):
    """A comparison score, not a correctness probability or extraction admission rule."""
    words, letters, score = 0, 0, 0.0
    for token, raw_confidence in zip(data.get("text", []), data.get("conf", []), strict=True):
        try:
            confidence = float(raw_confidence)
        except (ValueError, TypeError):
            continue
        token = token.strip()
        count = sum(char.isalpha() for char in token)
        if (
            not math.isfinite(confidence)
            or not MIN_WORD_CONFIDENCE <= confidence <= 100
            or count < 3
            or count < 0.6 * len(token)
        ):
            continue
        words += 1
        letters += count
        score += count * confidence / 100
    return dict(score=score, words=words, letters=letters)


def choose(candidates):
    """Require complete evidence, sufficient text and a distinct winner; otherwise abstain."""
    if {c.get("clockwise") for c in candidates} != {0, 90, 180, 270} or len(candidates) != 4:
        return None, "incomplete_rotation_comparison"
    if any(c.get("error") for c in candidates):
        return None, "rotation_probe_failed"
    if any(not math.isfinite(c["score"]) or c["score"] < 0 for c in candidates):
        return None, "invalid_rotation_evidence"
    first, second, *_ = sorted(candidates, key=lambda c: c["score"], reverse=True)
    if first["words"] < MIN_WORDS or first["letters"] < MIN_LETTERS:
        return None, "insufficient_readable_text"
    if first["score"] - second["score"] < MIN_SCORE_GAP or first["score"] < MIN_SCORE_RATIO * second["score"]:
        return None, "ambiguous_rotation_comparison"
    return first["clockwise"], "distinct_readable_text_evidence"


def detect(image, ocr, minimum_confidence):
    """Preserve the OSD result; use separate comparison evidence when it is weak."""
    rotation, confidence, error, elapsed = ocr.orientation(image)
    valid_osd = rotation in (0, 90, 180, 270) and math.isfinite(confidence) and not error
    accepted = valid_osd and confidence >= minimum_confidence
    result = dict(
        version=VERSION,
        method="osd",
        accepted=accepted,
        clockwise=rotation if accepted else None,
        osd_rotation_clockwise=rotation if valid_osd else None,
        osd_confidence=confidence if math.isfinite(confidence) else None,
        osd_min_confidence=minimum_confidence,
        osd_error=error,
        seconds=elapsed,
        status="accepted" if accepted else "osd_error" if error else "below_confidence_threshold",
        reason="osd_confidence_threshold" if accepted else "insufficient_osd_evidence",
        candidates=[],
    )
    if accepted or not callable(getattr(ocr, "orientation_evidence", None)):
        return result
    candidates, seconds = ocr.orientation_evidence(image)
    winner, reason = choose(candidates)
    result.update(
        method="ocr_comparison",
        accepted=winner is not None,
        clockwise=winner,
        status="accepted_ocr_comparison" if winner is not None else "unresolved_ocr_comparison",
        reason=reason,
        candidates=candidates,
        seconds=elapsed + seconds,
        policy=dict(
            min_words=MIN_WORDS,
            min_letters=MIN_LETTERS,
            min_word_confidence=MIN_WORD_CONFIDENCE,
            min_score_gap=MIN_SCORE_GAP,
            min_score_ratio=MIN_SCORE_RATIO,
            max_probe_side=MAX_SIDE,
            psm=11,
        ),
    )
    return result
