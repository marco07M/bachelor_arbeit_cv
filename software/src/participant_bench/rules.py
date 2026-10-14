"""Layout-based rows and columns, conservative signature-field inspection."""

import re
import time

import cv2
import numpy as np

from .ocr import grid_masks
from .schema import TEXT_FIELDS, Box, Participant, TextField


def token_key(text):
    return re.sub(r"[^a-zäöüß]", "", text.casefold())


def line_positions(mask, axis, fraction=0.25):
    indices = np.flatnonzero(np.mean(mask > 0, axis=axis) > fraction)
    if not len(indices):
        return []
    groups = np.split(indices, np.flatnonzero(np.diff(indices) > 2) + 1)
    size = mask.shape[0 if axis == 1 else 1]
    return [float(np.mean(group) / size) for group in groups]


def layout(image, data, config):
    _, horizontal, vertical = grid_masks(image)
    hlines = line_positions(horizontal, 1)
    vlines = line_positions(vertical, 0, 0.05)
    words = data["words"]
    headers = {}
    for word in words:
        key = token_key(word["text"])
        for field, aliases in config.rules.header_aliases.items():
            if key in {token_key(alias) for alias in aliases} and field not in headers:
                headers[field] = word
    columns = dict(config.rules.columns)
    anchors = sorted((w["bbox"]["x0"], name, w) for name, w in headers.items())
    for index, (x, name, word) in enumerate(anchors):
        if name in columns:
            continue
        # Use actual vertical separators where possible; otherwise header-derived intervals.
        lefts = [v for v in vlines if v <= x]
        rights = [v for v in vlines if v >= word["bbox"]["x1"]]
        if lefts and rights:
            columns[name] = (max(lefts), min(rights))
        else:
            left = max(0.0, x - 0.012)
            right = anchors[index + 1][0] - 0.012 if index + 1 < len(anchors) else 0.98
            if right > left:
                columns[name] = (left, right)
    top = config.rules.body_top
    if top is None:
        if len(headers) < 3:
            return [], columns, ["Insufficient headers; configure columns and body_top for this template"]
        top = max(w["bbox"]["y1"] for w in headers.values()) + 0.002
    bottom = config.rules.body_bottom
    rows = []
    boundaries = [v for v in hlines if v > top and v <= bottom]
    if len(boundaries) >= 2:
        rows = list(zip(boundaries[:-1], boundaries[1:]))
    else:
        body_words = sorted(
            (w for w in words if top < w["bbox"]["y0"] < bottom), key=lambda w: w["bbox"]["y0"]
        )
        groups = []
        for word in body_words:
            y = (word["bbox"]["y0"] + word["bbox"]["y1"]) / 2
            if not groups or abs(y - groups[-1][0]) > config.rules.row_tolerance:
                groups.append((y, [word]))
            else:
                groups[-1][1].append(word)
        rows = [
            (
                max(top, min(w["bbox"]["y0"] for w in group) - 0.003),
                min(bottom, max(w["bbox"]["y1"] for w in group) + 0.003),
            )
            for _, group in groups
        ]
    notes = [] if len(boundaries) >= 2 else ["Rows from word baselines; wrapped text may split participants"]
    return rows, columns, notes


def signature(image, box: Box | None, data, config):
    if box is None:
        return None, "uncertain", "Signature field could not be localized"
    width, height = image.size
    crop = image.crop((int(box.x0 * width), int(box.y0 * height), int(box.x1 * width), int(box.y1 * height)))
    ink, horizontal, vertical = grid_masks(crop)
    # Only remove geometric cell edges. An interior straight stroke may be content,
    # so deleting every long horizontal component could create a false blank decision.
    edge_h = max(2, int(ink.shape[0] * 0.10))
    edge_w = max(2, int(ink.shape[1] * 0.05))
    horizontal[edge_h:-edge_h, :] = 0
    vertical[:, edge_w:-edge_w] = 0
    cleaned = cv2.subtract(ink, cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((3, 3), np.uint8)))
    # Remove edge remnants, never erase OCR words: unexpected printed text requires review too.
    border = max(2, int(min(cleaned.shape) * 0.04))
    cleaned[:border] = cleaned[-border:] = 0
    cleaned[:, :border] = cleaned[:, -border:] = 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
    area = sum(
        int(stats[i, cv2.CC_STAT_AREA])
        for i in range(1, count)
        if stats[i, cv2.CC_STAT_AREA] >= config.signature.component_min_area
    )
    fraction = area / max(1, cleaned.size)
    if fraction <= config.signature.blank_ink_fraction:
        return False, "read", "Localized field blank after grid removal; inspect threshold on real scans"
    return None, "uncertain", "Ink/printed marks present; no validated positive signature classifier"


def extract_rules(image, data, config):
    start = time.perf_counter()
    rows, columns, notes = layout(image, data, config)
    participants, signature_seconds = [], 0.0
    for y0, y1 in rows:
        fields = {}
        for name in TEXT_FIELDS:
            if name not in columns:
                fields[name] = TextField(state="uncertain")
                continue
            x0, x1 = columns[name]
            box = Box(x0=x0, y0=y0, x1=x1, y1=y1)
            words = [
                w
                for w in data["words"]
                if x0 <= (w["bbox"]["x0"] + w["bbox"]["x1"]) / 2 < x1
                and y0 <= (w["bbox"]["y0"] + w["bbox"]["y1"]) / 2 < y1
            ]
            words.sort(key=lambda w: (round(w["bbox"]["y0"], 2), w["bbox"]["x0"]))
            value = " ".join(w["text"] for w in words)
            state = "read" if value else "empty"
            if words and any(w["ocr_confidence"] < 30 for w in words):
                state = "uncertain"
            fields[name] = TextField(value=value if value else None, state=state, bbox=box)
        if not any(f.value for f in fields.values()):
            continue
        row_ref = None
        if "row_ref" in columns:
            left, right = columns["row_ref"]
            candidates = [
                w["text"]
                for w in data["words"]
                if left <= w["bbox"]["x0"] < right
                and y0 <= w["bbox"]["y0"] < y1
                and re.fullmatch(r"\d+", w["text"])
            ]
            if len(candidates) == 1:
                row_ref = candidates[0]
        sig_box = None
        if "signature" in columns and not notes:
            sig_box = Box(x0=columns["signature"][0], y0=y0, x1=columns["signature"][1], y1=y1)
        sig_start = time.perf_counter()
        present, state, note = signature(image, sig_box, data, config)
        signature_seconds += time.perf_counter() - sig_start
        participants.append(
            Participant(
                row_ref=row_ref,
                bbox=Box(x0=0.0, y0=y0, x1=1.0, y1=y1),
                **fields,
                signature_present=present,
                signature_state=state,
                signature_bbox=sig_box,
                review_notes=notes + [note],
            )
        )
    return (
        participants,
        notes,
        {
            "structure_seconds": time.perf_counter() - start - signature_seconds,
            "signature_seconds": signature_seconds,
        },
    )


def attach_signatures(participants, image, data, config):
    """B uses its own participant locations; do not silently transfer A's participant assignment."""
    start = time.perf_counter()
    rows, columns, notes = layout(image, data, config)
    for participant in participants:
        box = participant.bbox
        sig_box = None
        if box and "signature" in columns and not notes:
            left, right = columns["signature"]
            matches = [
                (y0, y1)
                for y0, y1 in rows
                if min(y1, box.y1) - max(y0, box.y0) > 0.5 * min(y1 - y0, box.y1 - box.y0)
            ]
            if len(matches) == 1:
                y0, y1 = matches[0]
                sig_box = Box(x0=left, y0=y0, x1=right, y1=y1)
        present, state, note = signature(image, sig_box, data, config)
        participant.signature_present = present
        participant.signature_state = state
        participant.signature_bbox = sig_box
        participant.review_notes.append(note)
    return time.perf_counter() - start
