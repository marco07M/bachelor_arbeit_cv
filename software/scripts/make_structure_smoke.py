"""Small digital/scanned PDF fixture for real local Paddle/Docling adapter checks; synthetic people only."""

from pathlib import Path

import pymupdf
import yaml


def generate(root=Path("data/structure-smoke")):
    root.mkdir(parents=True, exist_ok=False)
    raw = root / "raw"
    raw.mkdir()
    source = pymupdf.open()
    cover = source.new_page()
    cover.insert_text((50, 80), "Synthetischer Test - Deckblatt", fontsize=17)
    page = source.new_page(width=842, height=595)
    page.insert_text((40, 45), "Teilnehmerliste - nur synthetische Testdaten", fontsize=17)
    columns = [40, 160, 320, 440, 560, 800]
    rows = [90, 135, 180, 225, 270]
    for y in rows:
        page.draw_line((columns[0], y), (columns[-1], y))
    for x in columns:
        page.draw_line((x, rows[0]), (x, rows[-1]))
    values = [
        ["Vorname", "Nachname", "Benutzer", "Kurzzeichen", "Unterschrift"],
        ["Anna", "Weber", "001234", "MUC", ""],
        ["Jörg", "Groß-Müller", "", "BER", ""],
        ["Lea", "Schmidt", "000789", "ABC-12", ""],
    ]
    for index, cells in enumerate(values):
        for column, cell in enumerate(cells):
            page.insert_text((columns[column] + 8, rows[index] + 28), cell, fontsize=12)
    pixmap = page.get_pixmap(dpi=220, alpha=False)
    scanned = source.new_page(width=842, height=595)
    scanned.insert_image(scanned.rect, pixmap=pixmap)
    scanned.set_rotation(90)
    source.save(raw / "123456.pdf")
    source.close()
    (root / "config.yaml").write_text(yaml.safe_dump({
        "extends": "../../configs/benchmark.yaml",
        "methods": ["ocr_raw", "paddle_llm", "docling"],
        "signature": {"backend": "opencv"},
        "pdf": {"dpi": 220, "recursive": True, "auto_orient": True},
    }), encoding="utf-8")
    return root


if __name__ == "__main__":
    print(generate())
