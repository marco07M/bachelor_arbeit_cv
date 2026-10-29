"""Experimental OCR image transforms with inverse coordinates; all options default off."""

import cv2
import numpy as np
from PIL import Image, ImageEnhance


def binary(image):
    gray = np.asarray(image.convert("L"))
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]


def grid_masks(image):
    ink = binary(image)
    h, w = ink.shape
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(30, w // 12)), np.uint8))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((max(30, h // 15), 1), np.uint8))
    return ink, horizontal, vertical


def remove_grid_lines(image):
    ink, horizontal, vertical = grid_masks(image)
    return Image.fromarray(255 - cv2.subtract(ink, cv2.bitwise_or(horizontal, vertical)))


def preprocess(image: Image.Image, spec):
    width, height = image.size
    region = spec.crop or (0, 0, 1, 1)
    left, top, right, bottom = (round(v * size) for v, size in zip(region, (width, height, width, height)))
    if right <= left or bottom <= top:
        raise ValueError("OCR crop is empty")
    source = image.crop((left, top, right, bottom)).convert("RGB")
    if spec.grayscale:
        source = source.convert("L")
    if spec.contrast != 1:
        source = ImageEnhance.Contrast(source).enhance(spec.contrast)
    if spec.scale != 1:
        source = source.resize(
            (max(1, round(source.width * spec.scale)), max(1, round(source.height * spec.scale)))
        )
    sx, sy = source.width / (right - left), source.height / (bottom - top)
    pixels = np.asarray(source).copy()
    if spec.denoise:
        pixels = cv2.medianBlur(pixels, spec.denoise)
    gray = pixels if pixels.ndim == 2 else cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    angle, inverse = 0.0, np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    if spec.deskew:
        ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
        ys, xs = np.nonzero(ink)
        if len(xs) >= 20:
            angle = float(cv2.minAreaRect(np.column_stack((xs, ys)).astype(np.float32))[-1])
            if angle > 45:
                angle -= 90
            if abs(angle) > spec.max_skew_degrees:
                angle = 0.0
        matrix = cv2.getRotationMatrix2D((source.width / 2, source.height / 2), angle, 1)
        inverse = cv2.invertAffineTransform(matrix)
        pixels = cv2.warpAffine(
            pixels,
            matrix,
            source.size,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255 if pixels.ndim == 2 else (255, 255, 255),
        )
        gray = pixels if pixels.ndim == 2 else cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    if spec.threshold == "otsu":
        pixels = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    elif spec.threshold == "adaptive":
        pixels = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)

    def original_box(x, y, w, h):
        corners = np.array([[x, y, 1], [x + w, y, 1], [x, y + h, 1], [x + w, y + h, 1]]) @ inverse.T
        xx = np.clip((corners[:, 0] / sx + left) / width, 0, 1)
        yy = np.clip((corners[:, 1] / sy + top) / height, 0, 1)
        return dict(x0=float(xx.min()), y0=float(yy.min()), x1=float(xx.max()), y1=float(yy.max()))

    return (
        Image.fromarray(pixels),
        original_box,
        {"deskew_degrees": angle, "crop_pixels": [left, top, right, bottom], "scale": [sx, sy]},
    )


def rotate_box(box: dict, degrees: int) -> dict:
    x0, y0, x1, y1 = (box[k] for k in ("x0", "y0", "x1", "y1"))
    values = {
        0: (x0, y0, x1, y1),
        90: (1 - y1, x0, 1 - y0, x1),
        180: (1 - x1, 1 - y1, 1 - x0, 1 - y0),
        270: (y0, 1 - x1, y1, 1 - x0),
    }
    return dict(zip(("x0", "y0", "x1", "y1"), values[degrees % 360]))
