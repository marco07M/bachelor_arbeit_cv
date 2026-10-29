"""Saved score explanations reconcile every contribution and never repair or re-run predictions."""

import base64
import csv
import hashlib
from html.parser import HTMLParser

import pytest

from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.roster_benchmark.cli import main
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.detail_report import render_details
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.schema import PageResult, VisualParticipant


def comparison(tmp_path, *, swapped=False, malicious=False, uncertain=False, source_error=False, best_fit=False):
    source = tmp_path / "source"
    first = '<img src=x onerror="alert(1)">' if malicious else "Anna"
    references = [["123456", "000007", first, "Weber", "MUC"]]
    if not swapped:
        references.extend([["123456", "000008", "Lina", "Berg", "ABC"],
                           ["123456", "", "Paula", "Mayer", "ABC"]])
    people = [VisualParticipant(first_name="Weber" if swapped else first if malicious else "Anma",
                                last_name=first if swapped else "Weber", personnel_number="" if swapped else "000007",
                                department="MUC").participant()]
    if not swapped:
        people.extend([VisualParticipant(first_name="Paula", last_name="Mayer", personnel_number="***", department="ABC").participant(),
                       VisualParticipant(first_name="Xenia", last_name="Mystery", personnel_number="000009", department="XYZ").participant()])
    config = BenchmarkConfig()
    if best_fit:
        config.matching.mode = "best_fit"
    if uncertain:
        people[0].first_name.state = "uncertain"
        config.matching.score_uncertain_values = False
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0001", page_number=1, method_id="vlm",
                      status="success", parse_status="valid", participants=people)
    if source_error:
        page.status, page.parse_status, page.participants = "failed", "invalid", []
        page.error = "Modellantwort am Ausgabelimit (2048 Token) abgeschnitten"
    write_json(source / "manifest.json", dict(inputs=[dict(kind="pdf", sha256="doc", path="123456.pdf")]))
    write_json(source / "summary.json", {"vlm": dict(status="success", output_kind="structured")})
    write_jsonl(source / "vlm/extractions.jsonl", [page.model_dump()])
    reference = tmp_path / "reference.csv"
    with reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows(references)
    output, metrics = evaluate_run(source, reference, config, tmp_path / "results")
    return output, metrics["vlm"], source, reference


def test_detail_export_reconciles_missing_extra_masked_and_fractional_fields(tmp_path):
    output, score, _, _ = comparison(tmp_path)
    checks = read_json(output / "details/calculation_checks.json")["vlm"]
    assert checks["contributions_match_saved_metrics"]
    assert checks["reference_fields"] == checks["predicted_fields"] == 11
    assert checks["similarity_credit"] == 6.75
    assert score["score_percent"] == pytest.approx(100 * 13.5 / 22)
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert "Anna" in page and "Anma" in page and "000007" in page
    assert "Referenzperson ohne Zuordnung" in page and "Ausgabe ohne Zuordnung" in page
    assert "Referenzwert fehlt oder ist maskiert" in page
    assert "1 − 1 / 4 = 0,75" in page
    assert "Alle 3 Referenzkandidaten" in page
    assert "Gewichtete Ähnlichkeit" in page and "Beitrag R" in page and "Beitrag P" in page
    assert 'href="details.html"' in (output / "report.html").read_text(encoding="utf-8")


def test_refresh_uses_frozen_reference_and_never_regrades_or_contacts_a_service(tmp_path, monkeypatch):
    output, _, source, reference = comparison(tmp_path)
    protected = [path for path in output.iterdir() if path.is_file() and path.suffix != ".html"]
    protected += list(source.rglob("*.json")) + list(source.rglob("*.jsonl"))
    before = {path: file_hash(path) for path in protected}
    reference.unlink()  # Prove that the current workbook is unnecessary for saved-score explanations.
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: pytest.fail("No network during rendering"))
    monkeypatch.setattr("participant_bench.roster_benchmark.cli.load_config", lambda *args: pytest.fail("No new config"))
    monkeypatch.setattr("participant_bench.roster_benchmark.evaluation.evaluate_run", lambda *args: pytest.fail("No regrading"))
    assert main(["details", "--report", str(output)]) == 0
    assert all(file_hash(path) == expected for path, expected in before.items())


def test_swapped_names_are_diagnostic_only_without_automatic_credit(tmp_path):
    output, score, source, _ = comparison(tmp_path, swapped=True)
    prediction_hash = file_hash(source / "vlm/extractions.jsonl")
    assert score["score_percent"] == 0 and score["assigned_participants"] == 0
    checks = read_json(output / "details/calculation_checks.json")["vlm"]
    assert checks["name_order_hints"] == 1 and checks["similarity_credit"] == 0
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert "Vertauschte Vor-/Nachnamensfelder" in page
    assert "keine Punkte hier" in page and "unter dem Mindestwert" in page
    assert file_hash(source / "vlm/extractions.jsonl") == prediction_hash


def test_raw_uncertain_text_remains_visible_when_excluded_from_grading(tmp_path):
    output, _, _, _ = comparison(tmp_path, uncertain=True)
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert "Anma" in page and "uncertain" in page and "Bewerteter Wert" in page
    assert read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]


def test_missing_source_still_explains_saved_csv_and_snapshot(tmp_path):
    output, _, _, _ = comparison(tmp_path)
    render_details(output, source_run=tmp_path / "unavailable")
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert "Rohvorhersage nicht verfügbar" in page and "Anma" in page
    assert read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]


def test_changed_source_predictions_are_not_silently_mixed_into_old_grading(tmp_path):
    output, _, source, _ = comparison(tmp_path)
    (source / "vlm/extractions.jsonl").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Quellvorhersagen"):
        render_details(output)


def test_inconsistent_saved_totals_are_flagged_without_replacing_metrics(tmp_path):
    output, _, _, _ = comparison(tmp_path)
    metrics = read_json(output / "metrics.json")
    metrics["methods"]["vlm"]["score_percent"] = 99
    write_json(output / "metrics.json", metrics)
    before = file_hash(output / "metrics.json")
    render_details(output)
    assert not read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]
    assert "ABWEICHUNG" in (output / "details.html").read_text(encoding="utf-8")
    assert file_hash(output / "metrics.json") == before


def test_sensitive_values_are_escaped_and_only_the_fixed_filter_script_can_execute(tmp_path):
    output, _, _, _ = comparison(tmp_path, malicious=True)
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in page

    class Inspect(HTMLParser):
        def __init__(self):
            super().__init__()
            self.policy, self.scripts, self.in_script, self.images = "", [], False, 0

        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
                self.policy = attrs["content"]
            if tag == "script":
                assert "src" not in attrs
                self.scripts.append("")
                self.in_script = True
            self.images += tag == "img"

        def handle_endtag(self, tag):
            if tag == "script":
                self.in_script = False

        def handle_data(self, data):
            if self.in_script:
                self.scripts[-1] += data

    parser = Inspect()
    parser.feed(page)
    assert not parser.images and len(parser.scripts) == 1
    fingerprint = base64.b64encode(hashlib.sha256(parser.scripts[0].encode()).digest()).decode()
    assert f"script-src 'sha256-{fingerprint}'" in parser.policy
    assert "connect-src 'none'" in parser.policy


def test_failed_source_page_and_output_limit_are_explained_without_losing_denominators(tmp_path):
    output, score, _, _ = comparison(tmp_path, source_error=True)
    assert score["score_percent"] == 0 and score["reference_participants"] == 3
    page = (output / "details.html").read_text(encoding="utf-8")
    assert "Ausgabelimit (2048 Token)" in page and "invalid" in page and "123456.pdf" in page
    checks = read_json(output / "details/calculation_checks.json")["vlm"]
    assert checks["reference_fields"] == 11 and checks["predicted_fields"] == 0
    assert checks["contributions_match_saved_metrics"]


def test_best_fit_report_keeps_conservative_baseline_and_explicit_review_flags(tmp_path):
    output, score, source, _ = comparison(tmp_path, swapped=True, best_fit=True)
    assert score["assigned_participants"] == 1 and score["score_percent"] > 0
    assert score["conservative_assigned_participants"] == 0 and score["conservative_score_percent"] == 0
    assert score["low_similarity_assignments"] == 1
    page = next((output / "details").glob("*.html")).read_text(encoding="utf-8")
    assert "Modus: globales Best-Fit" in page and "Schwache Paarung" in page
    assert "einschließlich lesbarer IDs" in page and "Prüfgrenzen (keine Sperre)" in page
    main = (output / "report.html").read_text(encoding="utf-8")
    assert "Konservativer Vergleich" in main and "bestätigen keine Identitäten" in main
    assert "best_fit" in (output / "participants.csv").read_text(encoding="utf-8-sig")
    assert read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]
    assert read_json(output / "config.json")["matching"]["mode"] == "best_fit"
    assert source.is_dir()
