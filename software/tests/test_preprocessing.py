import csv
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from participant_bench.config import load_config
from participant_bench.pdf import inventory
from vorverarbeitung import vorbereiten


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("12473.123456_12.23.1456_Muc.pdf", "123456"),
        ("12473.000007_12.23.1456_Muc.PDF", "000007"),
        ("12473.123456.pdf", "123456"),
        ("123456.pdf", "123456"),
        ("12473.123456.12.23.pdf", "123456"),
        ("12473.123456 12.23.1456_Muc.pdf", "123456"),
        ("12473.000007 12.23.1456_Muc.PDF", "000007"),
        ("12473_123456_12.23.1456_Muc.pdf", "123456"),
        ("01.12473.123456_12.23.1456_Muc.pdf", "123456"),
        ("12473. 123456_12.23.1456_Muc.pdf", "123456"),
        ("01.12473. 000007_12.23.1456_Muc.PDF", "000007"),
        ("01.12473_123456 12.23.1456_Muc.pdf", "123456"),
        ("12473_ 123456_12.23.1456_Muc.pdf", "123456"),
        ("101158 - 174563 - 09.09.2026 MUC.pdf", "174563"),
        ("101158-174563-09.09.2026 MUC.pdf", "174563"),
        ("101158 - 000007 - 09.09.2026 MUC.PDF", "000007"),
    ],
)
def test_document_number(filename, expected):
    assert vorbereiten.document_number(filename) == expected


@pytest.mark.parametrize(
    "filename", [
        "liste.pdf", "12473.abc_123456.pdf", "12473..123456.pdf", "12473.123abc_12.pdf",
        "12473.42_Muc.pdf", "12473.12345_Muc.pdf", "12473.00007_Muc.pdf",
        "12473.12345 12.23.1456_Muc.pdf", "12473.123abc 12.23.1456_Muc.pdf",
        "12473.1234567_Muc.pdf", "12473.1234567 12.23.1456_Muc.pdf",
        "12473_12345_12.23.1456_Muc.pdf", "01.12473.12345_12.23.1456_Muc.pdf",
        "12473. 1234567_12.23.1456_Muc.pdf", "01.12473.1234567_12.23.1456_Muc.pdf",
        "101158 - 17456 - 09.09.2026 MUC.pdf",
        "101158 - 1745637 - 09.09.2026 MUC.pdf",
        "101158 - abc - 09.09.2026 MUC.pdf",
        "101158 - 17456 - 999999 MUC.pdf",
    ]
)
def test_invalid_number_is_not_guessed(filename):
    with pytest.raises(ValueError):
        vorbereiten.document_number(filename)


def make_pdf(path, text="Teilnehmerliste"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), text)
        doc.save(path)


def test_recursive_copy_logs_and_handoff_to_processing(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    make_pdf(raw / "München" / "2026" / "12473.000007_12.23.1456_Muc.PDF")
    make_pdf(raw / "Berlin" / "12473.123456 12.23.1456_Ber.pdf")
    (raw / "notizen.docx").write_bytes(b"not a PDF")
    (raw / "ohne-nummer.pdf").write_bytes(b"unclassified PDF")
    originals = {p: p.read_bytes() for p in raw.rglob("*") if p.is_file()}

    report = vorbereiten.preprocess(raw, output)

    assert report["summary"] == {"skipped_non_pdf": 1, "copied_rejected": 1, "copied": 2}
    target = output / "pdfs" / "000007.pdf"
    assert target.read_bytes() == originals[raw / "München" / "2026" / "12473.000007_12.23.1456_Muc.PDF"]
    assert originals == {p: p.read_bytes() for p in originals}
    assert len(list((output / "pdfs").rglob("*.pdf"))) == 2
    assert (output / "pdfs" / "123456.pdf").is_file()
    assert all(path.is_file() for path in (output / "pdfs").iterdir())
    assert any("München" in entry["source"] for entry in report["entries"])
    assert (output / "nicht_erfuellt" / "ohne-nummer.pdf").read_bytes() == b"unclassified PDF"
    report_path = Path(report["report_path"])
    assert json.loads(report_path.read_text(encoding="utf-8"))["entries"] == report["entries"]
    with report_path.with_suffix(".csv").open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == report["entries"]
    config = load_config(Path("configs/imported.yaml"))
    assert config.methods == ["ocr_rules", "ocr_llm", "vlm"]
    assert len(inventory(output / "pdfs", config.pdf.recursive)) == 2


def test_dry_run_writes_nothing_and_predicts_conflict(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    raw.mkdir()
    (raw / "1.000007_a.pdf").write_bytes(b"first PDF")
    (raw / "2.000007_b.pdf").write_bytes(b"different PDF")
    report = vorbereiten.preprocess(raw, output, dry_run=True)
    assert report["summary"] == {"would_copy": 1, "conflict": 1}
    assert not output.exists()
    assert "report_path" not in report


def test_repeat_run_duplicate_and_existing_conflict_never_overwrite(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    raw.mkdir()
    (raw / "1.123456_a.pdf").write_bytes(b"original")
    (raw / "2.123456_b.pdf").write_bytes(b"original")
    (raw / "3.123456_c.pdf").write_bytes(b"other contents")
    first = vorbereiten.preprocess(raw, output)
    assert first["summary"] == {"copied": 1, "duplicate": 1, "conflict": 1}
    second = vorbereiten.preprocess(raw, output)
    assert second["summary"] == {"already_present": 1, "duplicate": 1, "conflict": 1}
    assert (output / "pdfs" / "123456.pdf").read_bytes() == b"original"
    (raw / "1.123456_a.pdf").write_bytes(b"changed source")
    third = vorbereiten.preprocess(raw, output)
    assert third["entries"][0]["status"] == "conflict"
    assert (output / "pdfs" / "123456.pdf").read_bytes() == b"original"
    assert len(list((output / "protokolle").glob("*.json"))) == 3


def test_same_number_in_different_folders_reports_conflict(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    for folder in ("A", "B"):
        (raw / folder).mkdir(parents=True)
        (raw / folder / "1.123456_a.pdf").write_bytes(folder.encode())
    preview = vorbereiten.preprocess(raw, output, dry_run=True)
    assert preview["summary"] == {"would_copy": 1, "conflict": 1}
    assert not output.exists()
    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"copied": 1, "conflict": 1}
    assert (output / "pdfs" / "123456.pdf").read_bytes() == b"A"
    assert [path.name for path in (output / "pdfs").iterdir()] == ["123456.pdf"]


def test_identical_number_and_content_across_folders_is_deduplicated(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    for folder in ("A", "B"):
        (raw / folder).mkdir(parents=True)
        (raw / folder / "1.123456 a.pdf").write_bytes(b"same content")
    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"copied": 1, "duplicate": 1}
    assert (output / "pdfs" / "123456.pdf").read_bytes() == b"same content"
    assert vorbereiten.preprocess(raw, output)["summary"] == {"already_present": 1, "duplicate": 1}


@pytest.mark.parametrize("output_kind", ["same", "child", "parent"])
def test_overlapping_directories_rejected(tmp_path, output_kind):
    raw = tmp_path / "dateien"
    raw.mkdir()
    output = {"same": raw, "child": raw / "ausgabe", "parent": tmp_path}[output_kind]
    with pytest.raises(ValueError, match="überlappen"):
        vorbereiten.preprocess(raw, output)


def test_copy_error_cleans_partial_file_and_continues(tmp_path, monkeypatch):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    raw.mkdir()
    (raw / "1.123456_a.pdf").write_bytes(b"source")
    (raw / "2.000007_a.pdf").write_bytes(b"other source")
    real_copy = vorbereiten.shutil.copyfileobj

    def fail_first(incoming, outgoing, **kwargs):
        if Path(incoming.name).name.startswith("1."):
            outgoing.write(b"partial")
            raise OSError("Disk write failed")
        return real_copy(incoming, outgoing, **kwargs)

    monkeypatch.setattr(vorbereiten.shutil, "copyfileobj", fail_first)
    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"error": 1, "copied": 1}
    assert not (output / "pdfs" / "123456.pdf").exists()
    assert (output / "pdfs" / "000007.pdf").read_bytes() == b"other source"


def test_standalone_cli_works_outside_software_directory(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    make_pdf(raw / "12473.123456_12.23.1456_Muc.pdf")
    command = [
        sys.executable, str(Path(vorbereiten.__file__).resolve()),
        "--input", str(raw), "--output", str(output),
    ]
    preview = subprocess.run(command + ["--dry-run"], cwd=tmp_path, capture_output=True)
    assert preview.returncode == 0, preview.stderr
    assert not output.exists()
    result = subprocess.run(command, cwd=tmp_path, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (output / "pdfs" / "123456.pdf").is_file()


def test_cli_sorts_bad_names_and_reports_empty_or_missing_input(tmp_path, capsys):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    command = ["--input", str(raw), "--output", str(output), "--dry-run"]
    assert vorbereiten.main(command) == 1
    raw.mkdir()
    assert vorbereiten.main(command) == 1
    make_pdf(raw / "ohne-nummer.pdf")
    assert vorbereiten.main(command) == 0
    assert "would_copy_rejected" in capsys.readouterr().out
    assert not output.exists()


def test_short_or_missing_ids_keep_original_names_in_flat_output(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    folder = raw / "München" / "2026"
    folder.mkdir(parents=True)
    contents = {
        "12473.12345_12.23.1456_Muc.pdf": b"five digits",
        "12473.00007_12.23.1456_Muc.PDF": b"five digits with leading zeros",
        "ohne-nummer.pdf": b"no number",
        "12473.abc_123456.pdf": b"invalid number",
    }
    for name, content in contents.items():
        (folder / name).write_bytes(content)
    preview = vorbereiten.preprocess(raw, output, dry_run=True)
    assert preview["summary"] == {"would_copy_rejected": 4}
    assert not output.exists()

    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"copied_rejected": 4}
    assert not (output / "pdfs").exists()
    for name, content in contents.items():
        assert (folder / name).read_bytes() == content
        assert (output / "nicht_erfuellt" / name).read_bytes() == content
    assert all(path.is_file() for path in (output / "nicht_erfuellt").iterdir())
    assert all(entry["reason"] for entry in report["entries"])
    assert any("genau 6" in entry["reason"] for entry in report["entries"])


    repeated = vorbereiten.preprocess(raw, output)
    assert repeated["summary"] == {"already_present": 4}
    assert all("; " in entry["reason"] for entry in repeated["entries"])

    # Auch aussortierte PDFs dürfen bei geändertem Inhalt kein Ziel überschreiben.
    changed_name = next(iter(contents))
    (folder / changed_name).write_bytes(b"changed")
    conflict = vorbereiten.preprocess(raw, output)
    assert conflict["summary"] == {"conflict": 1, "already_present": 3}
    assert (
        output / "nicht_erfuellt" / changed_name
    ).read_bytes() == contents[changed_name]


@pytest.mark.parametrize(
    ("filename", "expected"), [
        ("12473_123456_12.23.1456_Muc.pdf", "123456"),
        ("01.12473.123456_12.23.1456_Muc.pdf", "123456"),
        ("12473. 123456_12.23.1456_Muc.pdf", "123456"),
        ("101158 - 174563 - 09.09.2026 MUC.pdf", "174563"),
    ],
)
def test_alternative_filename_formats_are_copied_using_six_digit_id(tmp_path, filename, expected):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    raw.mkdir()
    (raw / filename).write_bytes(b"PDF contents")
    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"copied": 1}
    assert report["entries"][0]["number"] == expected
    assert (output / "pdfs" / f"{expected}.pdf").read_bytes() == b"PDF contents"


def test_rejected_same_name_from_different_folders_never_overwrites(tmp_path):
    raw, output = tmp_path / "dateien", tmp_path / "ausgabe"
    for folder in ("A", "B"):
        (raw / folder).mkdir(parents=True)
        (raw / folder / "ohne-nummer.pdf").write_bytes(folder.encode())
    report = vorbereiten.preprocess(raw, output)
    assert report["summary"] == {"copied_rejected": 1, "conflict": 1}
    assert (output / "nicht_erfuellt" / "ohne-nummer.pdf").read_bytes() == b"A"
