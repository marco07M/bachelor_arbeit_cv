"""The separate name report displays saved pairs and global decisions without changing grading."""

import base64
import csv
import hashlib
from html.parser import HTMLParser

import pytest
from test_benchmark_details import comparison

from participant_bench.io import file_hash, read_json, write_json, write_jsonl
from participant_bench.roster_benchmark.assignment_report import FILTER_SCRIPT, render_assignments
from participant_bench.roster_benchmark.cli import main
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import evaluate_run
from participant_bench.schema import PageResult, VisualParticipant


def test_name_report_shows_actual_pair_side_by_side_and_unmatched_names(tmp_path):
    output, _, _, _ = comparison(tmp_path)
    text = (output / "zuordnungen.html").read_text(encoding="utf-8")
    assert "<th>Erkannter Name</th>" in text and "<th>Name in Excel/CSV</th>" in text
    assert ('<td><strong>Vorname:</strong> Anma<br><strong>Nachname:</strong> Weber</td><td>→</td>'
            '<td><strong>Vorname:</strong> Anna<br><strong>Nachname:</strong> Weber') in text
    assert "User ID hatte im konservativen Modus Vorrang" in text
    assert "Keine Referenz zugeordnet" in text and "Keine Modellausgabe zugeordnet" in text
    assert 'id="names-method"' in text and 'id="names-search"' in text
    assert 'href="zuordnungen.html"' in (output / "report.html").read_text(encoding="utf-8")
    assert 'href="zuordnungen.html"' in (output / "details.html").read_text(encoding="utf-8")


def test_nonlocal_best_candidate_is_explained_by_saved_global_assignment(tmp_path):
    source = tmp_path / "source"
    people = [VisualParticipant(first_name=name, last_name="Test", personnel_number="", department="MUC").participant()
              for name in ("Annika", "Anna")]
    page = PageResult(run_id="fixture", document_id="doc", page_id="doc-p0001", page_number=1, method_id="vlm",
                      status="success", parse_status="valid", participants=people)
    write_json(source / "manifest.json", dict(inputs=[dict(kind="pdf", sha256="doc", path="123456.pdf")]))
    write_json(source / "summary.json", {"vlm": dict(status="success", output_kind="structured")})
    write_jsonl(source / "vlm/extractions.jsonl", [page.model_dump()])
    reference = tmp_path / "reference.csv"
    with reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Class ID", "User ID", "First Name", "Last Name", "Organization"])
        writer.writerows([["123456", "", name, "Test", "MUC"] for name in ("Anna", "Anja")])
    config = BenchmarkConfig()
    config.matching.mode = "best_fit"
    output, _ = evaluate_run(source, reference, config, tmp_path / "results")
    with (output / "participants.csv").open(encoding="utf-8-sig", newline="") as stream:
        cases = list(csv.DictReader(stream))
    assert next(case for case in cases if case["output_index"] == "0")["reference_row"] == "3"
    text = (output / "zuordnungen.html").read_text(encoding="utf-8")
    assert "lokal Rang 2" in text
    assert "Ein anderer Name ist lokal ähnlicher" in text
    assert "Anderer Ausgabe zugeordnet" in text and "gespeicherte globale Optimierungswert" in text
    assert "Annika" in text and "Anja" in text


def test_refresh_preserves_all_data_and_never_recomputes_pairs_or_reads_current_reference(tmp_path, monkeypatch):
    output, _, source, reference = comparison(tmp_path, best_fit=True)
    files = [p for p in output.iterdir() if p.is_file() and p.suffix != ".html"] + list(source.rglob("*.jsonl"))
    before = {p: file_hash(p) for p in files}
    reference.unlink()
    monkeypatch.setattr("participant_bench.roster_benchmark.matching.align", lambda *a, **k: pytest.fail("No new assignment"))
    monkeypatch.setattr("participant_bench.roster_benchmark.cli.load_config", lambda *a: pytest.fail("No current config"))
    monkeypatch.setattr("socket.create_connection", lambda *a, **k: pytest.fail("No network"))
    assert main(["assignments", "--report", str(output)]) == 0
    assert all(file_hash(p) == expected for p, expected in before.items())
    assert read_json(output / "config.json")["matching"]["mode"] == "best_fit"


def test_original_uncertain_names_are_visible_separately_from_evaluated_fields(tmp_path):
    output, _, _, _ = comparison(tmp_path, uncertain=True)
    text = (output / "zuordnungen.html").read_text(encoding="utf-8")
    assert "<strong>Vorname:</strong> Anma" in text and "uncertain" in text
    assert "Bewertung nach Normalisierung" in text and "Anna" in text


def test_missing_source_falls_back_to_saved_values_but_changed_source_is_rejected(tmp_path):
    output, _, source, _ = comparison(tmp_path)
    render_assignments(output, source_run=tmp_path / "not-present")
    assert "Anma" in (output / "zuordnungen.html").read_text(encoding="utf-8")
    (source / "vlm/extractions.jsonl").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Quellvorhersagen"):
        render_assignments(output)


def test_name_values_are_inert_and_filter_code_has_a_fixed_csp_hash(tmp_path):
    output, _, _, _ = comparison(tmp_path, malicious=True)
    text = (output / "zuordnungen.html").read_text(encoding="utf-8")
    assert '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;' in text

    class Inspect(HTMLParser):
        images = 0
        policy = ""

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            self.images += tag == "img"
            if tag == "meta" and values.get("http-equiv") == "Content-Security-Policy":
                self.policy = values["content"]

    inspected = Inspect()
    inspected.feed(text)
    assert inspected.images == 0
    fingerprint = base64.b64encode(hashlib.sha256(FILTER_SCRIPT.encode()).digest()).decode()
    assert f"script-src 'sha256-{fingerprint}'" in inspected.policy
    assert "connect-src 'none'" in inspected.policy
