import subprocess
import sys
from pathlib import Path

import numpy as np
import pymupdf

from participant_bench.io import file_hash, read_json
from vorverarbeitung import vorbereiten


def assert_page_content_unchanged(before, old, after, new):
    assert [before.xref_stream(x) for x in old.get_contents()] == [after.xref_stream(x) for x in new.get_contents()]
    old_pixels = np.frombuffer(old.get_pixmap(annots=False).samples, dtype=np.uint8).astype(np.int16)
    new_pixels = np.frombuffer(new.get_pixmap(annots=False).samples, dtype=np.uint8).astype(np.int16)
    # MuPDF glyph antialiasing can differ by 1–2 levels after resource renumbering.
    delta = np.abs(old_pixels - new_pixels)
    assert delta.max() <= 3
    assert delta.mean() < 0.01


def annotated_pdf(path: Path, text="Anna Weber 00007 ABC", *, redaction=False) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 60), text)
        page.draw_line((40, 100), (300, 100))  # Actual page content, not an annotation.
        page.add_highlight_annot(page.search_for("Anna") or pymupdf.Rect(50, 48, 100, 65))
        page.add_text_annot((100, 140), "Kommentar")
        page.add_line_annot((50, 180), (150, 180))
        if redaction:
            page.add_redact_annot(pymupdf.Rect(100, 45, 160, 65), fill=(0, 0, 0))
        page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(50, 200, 150, 220), "uri": "https://example.invalid"})
        widget = pymupdf.Widget()
        widget.field_name = "Testfeld"
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect = pymupdf.Rect(50, 250, 200, 280)
        widget.field_value = "Erhalten"
        page.add_widget(widget)
        second = document.new_page()
        second.insert_text((50, 60), "Zweite Seite")
        second.add_underline_annot(second.search_for("Zweite"))
        second.set_rotation(90)
        document.save(path)
    return path.read_bytes()


def test_cleanup_preserves_original_text_layout_widgets_and_rotation(tmp_path, capsys):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    source = raw / "123456.pdf"
    original = annotated_pdf(source)
    report = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert report["summary"] == {"copied": 1}
    entry = report["entries"][0]
    assert entry["annotations_removed"] == 4
    assert entry["redactions_preserved"] == 0
    assert source.read_bytes() == original
    archived = output / entry["original_destination"]
    edited = output / entry["comparison_destination"]
    assert archived.read_bytes() == original
    assert archived.name == source.name
    assert edited.name == "123456_bearbeitet.pdf"
    assert edited.parent == archived.parent
    assert edited.read_bytes() == (output / "pdfs" / "123456.pdf").read_bytes()
    assert file_hash(output / "pdfs" / "123456.pdf") == entry["output_sha256"]
    assert entry["output_sha256"] != entry["sha256"]
    with pymupdf.open(source) as before, pymupdf.open(output / "pdfs" / "123456.pdf") as after:
        assert before.page_count == after.page_count == 2
        for old, new in zip(before, after):
            assert not list(new.annots() or [])
            assert new.get_text() == old.get_text()
            assert new.rotation == old.rotation
            assert_page_content_unchanged(before, old, after, new)
        assert len(after[0].get_links()) == 1
        assert [widget.field_value for widget in after[0].widgets()] == ["Erhalten"]
    saved = read_json(Path(report["report_path"]))
    assert saved["remove_annotations"] is True
    assert saved["entries"] == report["entries"]
    vorbereiten.print_summary(report)
    summary = capsys.readouterr().out
    assert "Anmerkungen entfernt:" in summary and "Originale neu gesichert:" in summary


def test_repeat_is_idempotent_and_each_source_keeps_its_own_pair(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    original = annotated_pdf(raw / "1.123456_a.pdf")
    (raw / "2.123456_b.pdf").write_bytes(original)
    first = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert first["summary"] == {"copied": 1, "duplicate": 1}
    output_bytes = (output / "pdfs" / "123456.pdf").read_bytes()
    repeated = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert repeated["summary"] == {"already_present": 1, "duplicate": 1}
    assert (output / "pdfs" / "123456.pdf").read_bytes() == output_bytes
    assert len(list((output / "vergleich").iterdir())) == 2
    for source, entry in zip(sorted(raw.iterdir()), repeated["entries"]):
        archived, edited = output / entry["original_destination"], output / entry["comparison_destination"]
        assert archived.name == source.name
        assert archived.read_bytes() == original
        assert edited.read_bytes() == output_bytes
        assert archived.parent == edited.parent
        assert entry["original_status"] == entry["comparison_status"] == "already_present"


def test_dry_run_detects_annotations_and_conflicts_without_writes(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    annotated_pdf(raw / "1.123456_a.pdf")
    annotated_pdf(raw / "2.123456_b.pdf", text="Ben Fischer 00008 XYZ")
    preview = vorbereiten.preprocess(raw, output, remove_annotations=True, dry_run=True)
    assert preview["summary"] == {"would_copy": 1, "conflict": 1}
    assert preview["entries"][0]["annotations_removed"] == 4
    assert not output.exists()
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"copied": 1, "conflict": 1}
    assert len(list((output / "vergleich").iterdir())) == 2
    for entry in result["entries"]:
        assert (output / entry["comparison_destination"]).is_file()


def test_earlier_original_copy_is_upgraded_after_archiving(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    original = annotated_pdf(raw / "1.123456_a.pdf")
    vorbereiten.preprocess(raw, output)
    target = output / "pdfs" / "123456.pdf"
    preview = vorbereiten.preprocess(raw, output, remove_annotations=True, dry_run=True)
    assert preview["summary"] == {"would_update": 1}
    assert target.read_bytes() == original
    assert not (output / "vergleich").exists()
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"updated": 1}
    assert target.read_bytes() != original
    entry = result["entries"][0]
    assert (output / entry["original_destination"]).read_bytes() == original


def test_redaction_annotations_and_applied_redactions_remain(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    source = raw / "1.123456_a.pdf"
    annotated_pdf(source, redaction=True)
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["entries"][0]["redactions_preserved"] == 1
    with pymupdf.open(output / "pdfs" / "123456.pdf") as document:
        assert [annot.type[0] for annot in document[0].annots()] == [pymupdf.PDF_ANNOT_REDACT]

    # An applied redaction is actual document content, which the cleanup must retain.
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 60), "Verdeckte Nummer")
        page.add_redact_annot(page.search_for("Nummer")[0], fill=(0, 0, 0))
        page.apply_redactions()
        page.add_highlight_annot(page.search_for("Verdeckte")[0])
        document.save(raw / "1.654321_b.pdf")
    vorbereiten.preprocess(raw, output, remove_annotations=True)
    with pymupdf.open(raw / "1.654321_b.pdf") as before, pymupdf.open(output / "pdfs" / "654321.pdf") as after:
        assert "Nummer" not in after[0].get_text()
        assert_page_content_unchanged(before, before[0], after, after[0])


def test_rejected_filename_is_also_cleaned_and_backed_up(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    original = annotated_pdf(raw / "ohne-nummer.pdf")
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"copied_rejected": 1}
    entry = result["entries"][0]
    assert (output / entry["original_destination"]).read_bytes() == original
    with pymupdf.open(output / "nicht_erfuellt" / "ohne-nummer.pdf") as document:
        assert not list(document[0].annots() or [])


def test_broken_and_encrypted_pdfs_are_archived_and_do_not_stop_good_file(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    raw.mkdir()
    (raw / "1.123456_broken.pdf").write_bytes(b"not a PDF")
    with pymupdf.open() as document:
        document.new_page()
        document.save(raw / "1.000007_locked.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256,
                      owner_pw="owner", user_pw="secret")
    annotated_pdf(raw / "1.654321_good.pdf")
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"error": 2, "copied": 1}
    assert len(list((output / "vergleich").iterdir())) == 3
    for entry in result["entries"]:
        assert (output / entry["original_destination"]).is_file()
        assert (output / entry["comparison_destination"]).exists() == (entry["status"] == "copied")
    assert (output / "pdfs" / "654321.pdf").exists()


def test_different_existing_target_and_tampered_archive_are_not_overwritten(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    source = raw / "123456.pdf"
    original = annotated_pdf(source)
    target = output / "pdfs" / "123456.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"different existing file")
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"conflict": 1}
    assert target.read_bytes() == b"different existing file"
    archive = output / result["entries"][0]["original_destination"]
    assert archive.read_bytes() == original
    archive.write_bytes(b"tampered")
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"error": 1}
    assert archive.read_bytes() == b"tampered"
    assert source.read_bytes() == original


def test_cli_cleanup_is_default_and_copy_only_is_explicit(tmp_path):
    raw = tmp_path / "eingabe"
    original = annotated_pdf(raw / "123456.pdf")
    command = [sys.executable, str(Path(vorbereiten.__file__).resolve()), "--input", str(raw)]
    output = tmp_path / "cleaned"
    process = subprocess.run(command + ["--output", str(output)], cwd=tmp_path, capture_output=True)
    assert process.returncode == 0, process.stderr
    assert (output / "pdfs" / "123456.pdf").read_bytes() != original
    assert len(list((output / "vergleich").iterdir())) == 1
    output = tmp_path / "copied"
    process = subprocess.run(command + ["--output", str(output), "--keep-annotations"], cwd=tmp_path, capture_output=True)
    assert process.returncode == 0, process.stderr
    assert (output / "pdfs" / "123456.pdf").read_bytes() == original


def test_identical_original_names_in_different_folders_get_separate_pairs(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    name = "12473.123456_12.23.1456_Muc.PDF"
    original = annotated_pdf(raw / "A" / name)
    (raw / "B").mkdir()
    (raw / "B" / name).write_bytes(original)
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"copied": 1, "duplicate": 1}
    directories = set()
    for entry in result["entries"]:
        archived, edited = output / entry["original_destination"], output / entry["comparison_destination"]
        assert archived.name == name
        assert archived.read_bytes() == original
        assert edited.parent == archived.parent
        assert edited.read_bytes() == (output / "pdfs" / "123456.pdf").read_bytes()
        directories.add(archived.parent)
    assert len(directories) == 2


def test_pair_names_never_collide_even_for_rejected_original_filename(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    original = annotated_pdf(raw / "dokument_bearbeitet.pdf")
    result = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert result["summary"] == {"copied_rejected": 1}
    entry = result["entries"][0]
    archived, edited = output / entry["original_destination"], output / entry["comparison_destination"]
    assert archived.name == "dokument_bearbeitet.pdf"
    assert archived.read_bytes() == original
    assert edited != archived
    assert edited.read_bytes() != original


def test_edited_comparison_is_not_overwritten_after_manual_changes(tmp_path):
    raw, output = tmp_path / "eingabe", tmp_path / "ausgabe"
    original = annotated_pdf(raw / "1.123456.pdf")
    first = vorbereiten.preprocess(raw, output, remove_annotations=True)
    entry = first["entries"][0]
    edited = output / entry["comparison_destination"]
    edited.write_bytes(b"manual changes")
    repeated = vorbereiten.preprocess(raw, output, remove_annotations=True)
    assert repeated["summary"] == {"error": 1}
    assert edited.read_bytes() == b"manual changes"
    assert (output / entry["original_destination"]).read_bytes() == original
