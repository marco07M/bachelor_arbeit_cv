"""One frozen random PDF subset, before rendering, shared across methods and resumed unchanged."""

import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pymupdf
import pytest
from test_roster_benchmark import write_reference

from participant_bench.config import load_config
from participant_bench.document_sampling import annotate_report, ask_count, make_sample, selected_inputs
from participant_bench.io import file_hash, read_json
from participant_bench.pdf import inventory, prepare, validate_manifest
from participant_bench.roster_benchmark import cli, runner
from participant_bench.roster_benchmark.config import BenchmarkConfig
from participant_bench.roster_benchmark.evaluation import map_documents


def pool(n=8):
    return [dict(path=f"{i:06}.pdf", kind="pdf", sha256=f"hash-{i}") for i in range(n)]


def test_seed_selects_exact_count_without_mutating_pool_and_is_order_independent():
    inputs = pool()
    old = deepcopy(inputs)
    sample = make_sample(inputs, 3, 42)
    assert len(selected_inputs(inputs, sample)) == 3 and inputs == old
    assert sample == make_sample(inputs, 3, 42)
    assert (
        sample["selected_document_ids"] == make_sample(list(reversed(inputs)), 3, 42)["selected_document_ids"]
    )


@pytest.mark.parametrize("count", [0, -1, 9, 1.2, True])
def test_invalid_count_is_rejected(count):
    with pytest.raises(ValueError, match="Dokumentanzahl"):
        make_sample(pool(), count)


def test_fresh_seed_and_duplicate_aliases_remain_visible(monkeypatch):
    monkeypatch.setattr("participant_bench.document_sampling.secrets.randbits", lambda n: 12345)
    inputs = pool(2)
    inputs.append(dict(inputs[0], path="different-course.pdf"))
    sample = make_sample(inputs, 2)
    assert sample["seed"] == 12345 and sample["available_documents"] == 2
    assert (
        len(selected_inputs(inputs, sample)) == 3
    )  # Identical aliases cannot hide conflicting course names.
    with pytest.raises(ValueError):
        make_sample(inputs, 3)


@pytest.mark.parametrize("answer,expected", [("", None), ("alle", None), ("3", 3)])
def test_interactive_defaults_and_count(monkeypatch, answer, expected):
    monkeypatch.setattr("builtins.input", lambda text: answer)
    assert ask_count(5) == expected


def test_invalid_interactive_answers_are_requested_again_and_eof_does_not_start_all(monkeypatch):
    answers = iter(["nonsense", "0", "10", "2"])
    monkeypatch.setattr("builtins.input", lambda text: next(answers))
    assert ask_count(3) == 2

    def eof(text):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    with pytest.raises(ValueError, match="Keine Eingabe"):
        ask_count(3)


def pdf_pool(tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for i in range(4):
        with pymupdf.open() as pdf:
            for n in range(2):
                pdf.new_page().insert_text((30, 70), f"Synthetic document {i}, page {n}")
            pdf.save(folder / f"{123456 + i}.pdf")
    return folder


def test_only_selected_pdfs_are_opened_and_all_their_pages_are_kept(tmp_path, monkeypatch):
    folder = pdf_pool(tmp_path)
    config = load_config(Path("configs/smoke.yaml"))
    config.pdf.auto_orient = False
    original = {p: file_hash(p) for p in folder.iterdir()}
    sample = make_sample(inventory(folder, config.pdf.recursive), 3, 42)
    opened, original_open = [], pymupdf.open

    def track(path, *args, **kwargs):
        opened.append(str(path))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("participant_bench.pdf.pymupdf.open", track)
    manifest = prepare(folder, config, tmp_path / "prepared", document_sample=sample)
    assert len(opened) == 3 and {r["path"] for r in manifest["inputs"]} == set(opened)
    assert len(manifest["pages"]) == 6 and all(p["include"] for p in manifest["pages"])
    assert manifest["automatic_page_selection"] is False and not manifest["curated"]
    assert original == {p: file_hash(p) for p in folder.iterdir()}
    path = tmp_path / "prepared/manifest.json"
    assert validate_manifest(path, folder, config) == manifest
    # Even the excluded pool is frozen; resume must not silently redraw from a changed pool.
    extra = next(p for p in folder.iterdir() if str(p.resolve()) not in set(opened))
    extra.write_bytes(b"Changed excluded PDF")
    with pytest.raises(ValueError, match="Auswahl"):
        validate_manifest(path, folder, config)


def test_tampered_selection_is_rejected_and_course_alias_ambiguity_is_preserved():
    inputs = [
        dict(kind="pdf", path="123456.pdf", sha256="same"),
        dict(kind="pdf", path="654321.pdf", sha256="same"),
    ]
    sample = make_sample(inputs, 1, 42)
    _, documents, _ = map_documents(dict(inputs=selected_inputs(inputs, sample)), {"123456", "654321"})
    assert documents[0]["status"] == "ambiguous_document_course"
    sample["seed"] = -1
    with pytest.raises(ValueError):
        selected_inputs(inputs, sample)


def mocked_framework(tmp_path, monkeypatch):
    pdf_pool(tmp_path)
    write_reference(tmp_path / "reference.csv")
    (tmp_path / "models.yaml").write_text("methods: [ocr_raw, ocr_rules]\n", encoding="utf-8")
    config = BenchmarkConfig(
        input_dir="pdfs", reference_file="reference.csv", extraction_config="models.yaml"
    )
    calls = []

    def extract(config, folder, **kwargs):
        calls.append(dict(config=config, folder=folder, **kwargs))
        return tmp_path / "source", {}

    monkeypatch.setattr(runner, "extract", extract)
    monkeypatch.setattr(runner, "evaluate_run", lambda *a, **kw: (tmp_path / "report", {}))
    return config, calls


def test_framework_freezes_one_sample_for_all_methods_before_extraction(tmp_path, monkeypatch):
    config, calls = mocked_framework(tmp_path, monkeypatch)
    runner.run_benchmark(config, tmp_path, documents=3, sample_seed=42)
    assert len(calls) == 1 and calls[0]["config"].methods == ["ocr_raw", "ocr_rules"]
    sample = calls[0]["document_sample"]
    assert len(sample["selected_document_ids"]) == 3
    assert calls[0]["folder"] == tmp_path / "pdfs" and "reference" not in calls[0]


def test_enter_uses_legacy_all_documents_and_resume_never_prompts(tmp_path, monkeypatch):
    config, calls = mocked_framework(tmp_path, monkeypatch)
    monkeypatch.setattr("builtins.input", lambda text: "")
    runner.run_benchmark(config, tmp_path, prompt_documents=True)
    assert "document_sample" not in calls[0]
    monkeypatch.setattr(runner, "ask_count", lambda *a: pytest.fail("resume prompted/redrew"))
    runner.run_benchmark(config, tmp_path, prompt_documents=True, resume=tmp_path / "old-run")
    assert "document_sample" not in calls[1]


@pytest.mark.parametrize("option", ["resume", "manifest_path"])
def test_explicit_sample_cannot_replace_resume_or_existing_manifest(tmp_path, option):
    with pytest.raises(ValueError, match="gespeicherte Dokumentauswahl"):
        runner.run_benchmark(BenchmarkConfig(), tmp_path, documents=3, **{option: tmp_path / "old"})


def test_cli_forwards_explicit_count_seed_and_all_disables_prompt(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(cli, "run_benchmark", lambda *a, **kw: calls.append(kw) or (tmp_path, {}))
    assert (
        cli.main(
            ["run", "--config", str(config), "--prompt-documents", "--documents", "3", "--sample-seed", "42"]
        )
        == 0
    )
    assert calls[0]["documents"] == 3 and calls[0]["sample_seed"] == 42
    assert cli.main(["run", "--config", str(config), "--prompt-documents", "--all-documents"]) == 0
    assert "prompt_documents" not in calls[1] and "documents" not in calls[1]


def test_report_preserves_selection_provenance_without_touching_metrics(tmp_path):
    inputs = pool(4)
    inputs[0]["path"] = "123456<&>.pdf"
    sample = make_sample(inputs, 4, 42)
    for name in ("report.html", "standard_report.html"):
        (tmp_path / name).write_text("<h1>Test</h1><p>Metrics remain unchanged.</p>", encoding="utf-8")
    annotate_report(tmp_path, dict(document_sample=sample))
    before = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "4 von 4" in before and "Seed 42" in before and "123456&lt;&amp;&gt;.pdf" in before
    assert read_json(tmp_path / "document_sample.json") == sample
    annotate_report(tmp_path, dict(document_sample=sample))
    assert (tmp_path / "report.html").read_text(encoding="utf-8") == before


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CMD starter")
def test_five_method_cmd_exposes_options_without_running_models():
    result = subprocess.run(
        [shutil.which("cmd"), "/d", "/c", "start_testframework_5.cmd", "--help"],
        input="\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "--documents" in result.stdout and "--sample-seed" in result.stdout
