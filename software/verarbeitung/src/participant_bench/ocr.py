"""One shared OCR representation for A and B, including normalized word positions."""

import re
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from .doctor import tesseract_command
from .image_preprocessing import preprocess, rotate_box
from .io import digest, file_hash, read_json, write_json


def generated_cache_files(root):
    files = []
    for path in root.glob("*.json"):
        if path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", path.stem):
            continue
        try:
            data = read_json(path)
            if data.get("cache_key") == path.stem and "identity" in data and "words" in data:
                files.append(path)
        except (OSError, ValueError):
            pass
    return files


def binary(image):
    gray = np.asarray(image.convert("L"))
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]


def grid_masks(image):
    ink = binary(image)
    h, w = ink.shape
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(30, w // 12)), np.uint8))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((max(30, h // 15), 1), np.uint8))
    return ink, horizontal, vertical


class OCR:
    def __init__(self, config):
        self.config = config
        self.command = tesseract_command(config)
        pytesseract.pytesseract.tesseract_cmd = self.command
        language_result = subprocess.run(
            [self.command, "--list-langs"], capture_output=True, text=True, check=True, timeout=15
        )
        languages = language_result.stdout.splitlines()[1:]
        missing = set(config.ocr.languages.split("+")) - set(languages)
        if missing:
            raise FileNotFoundError(f"Tesseract languages missing: {sorted(missing)}")
        # Hash executable and installed language data, so a changed OCR installation invalidates cache.
        location = re.search(r'"([^"]+)"', language_result.stdout.splitlines()[0])
        trained = Path(location.group(1)) if location else Path(self.command).parent / "tessdata"
        if not trained.is_dir():
            raise FileNotFoundError(
                "Cannot identify effective Tesseract traineddata directory from --list-langs"
            )
        self.identity = {
            "version": str(pytesseract.get_tesseract_version()),
            "executable": file_hash(Path(self.command)),
            "languages": {p.name: file_hash(p) for p in trained.glob("*.traineddata")},
            "tessdata_path": str(trained.resolve()),
        }
        self.cache = Path(config.cache_dir) / "ocr"
        self.cache.mkdir(parents=True, exist_ok=True)

    def recognize(self, image: Image.Image, image_hash: str, *, embedded_words=None, rotation_clockwise=0):
        key = digest(
            {
                "image": image_hash,
                "config": self.config.ocr.model_dump(),
                "ocr": self.identity,
                "implementation": "ocr-v2-preprocessing",
                "embedded_words": embedded_words, "rotation": rotation_clockwise,
            }
        )
        cache_path = self.cache / f"{key}.json"
        if cache_path.is_file():
            result = read_json(cache_path)
            result["cache_hit"] = True
            return result
        start = time.perf_counter()
        if self.config.ocr.source == "prefer_pdf" and embedded_words and len(embedded_words) >= 3:
            usable = all(w["text"].strip() and "\ufffd" not in w["text"] for w in embedded_words)
            if usable:
                words = [dict(w, bbox=rotate_box(w["bbox"], rotation_clockwise), ocr_confidence=None) for w in embedded_words]
                result = {"words": words, "text": " ".join(w["text"] for w in words), "elapsed_seconds": time.perf_counter() - start,
                          "cache_hit": False, "cache_key": key, "identity": self.identity, "size": list(image.size),
                          "text_source": "pdf_text", "preprocessing": {"applied": False}}
                write_json(cache_path, result)
                self.enforce_limit()
                return result
        source, original_box, preprocessing = preprocess(image, self.config.ocr.preprocessing)
        if self.config.ocr.remove_grid_lines:
            ink, horizontal, vertical = grid_masks(source)
            lines = cv2.bitwise_or(horizontal, vertical)
            cleaned = Image.fromarray(255 - cv2.subtract(ink, lines))
            source.close()
            source = cleaned
        try:
            data = pytesseract.image_to_data(
                source,
                lang=self.config.ocr.languages,
                config=f"--psm {self.config.ocr.psm}",
                output_type=pytesseract.Output.DICT,
                timeout=self.config.ocr.timeout_seconds,
            )
        finally:
            source.close()
        w, h = image.size
        words = []
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            x, y, width, height = (data[k][i] for k in ("left", "top", "width", "height"))
            words.append(
                {
                    "text": text,
                    "bbox": original_box(x, y, width, height),
                    "ocr_confidence": float(data["conf"][i]),
                    "line": [data[k][i] for k in ("block_num", "par_num", "line_num")],
                }
            )
        result = {
            "words": words,
            "text": " ".join(w["text"] for w in words),
            "elapsed_seconds": time.perf_counter() - start,
            "cache_hit": False,
            "cache_key": key,
            "identity": self.identity,
            "size": [w, h],
            "text_source": "tesseract", "preprocessing": preprocessing,
        }
        write_json(cache_path, result)
        self.enforce_limit()
        return result

    def enforce_limit(self):
        files = sorted(generated_cache_files(self.cache), key=lambda p: p.stat().st_mtime)
        size = sum(p.stat().st_size for p in files)
        limit = self.config.cache_max_gb * 1024**3
        for path in files:
            if size <= limit:
                break
            if path.is_symlink():
                continue
            size -= path.stat().st_size
            path.unlink()

    def orientation(self, image):
        start = time.perf_counter()
        try:
            result = pytesseract.image_to_osd(
                image, output_type=pytesseract.Output.DICT, timeout=self.config.ocr.timeout_seconds
            )
            confidence = float(result["orientation_conf"])
            return int(result["rotate"]), confidence, None, time.perf_counter() - start
        except (pytesseract.TesseractError, RuntimeError) as exc:
            return 0, 0.0, str(exc), time.perf_counter() - start
