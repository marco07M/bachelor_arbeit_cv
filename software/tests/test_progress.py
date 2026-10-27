import threading
from pathlib import Path

import pymupdf
import pytest

from participant_bench.config import load_config
from participant_bench.io import file_hash, write_json
from participant_bench.models import Unavailable, local_model_identity
from participant_bench.pdf import prepare
from participant_bench.progress import Progress


def test_activity_reports_while_work_is_running_and_stops_its_thread(tmp_path, capsys):
    heartbeat = threading.Event()

    class ObservedProgress(Progress):
        def log(self, message):
            super().log(message)
            if "läuft weiter" in message:
                heartbeat.set()

    path = tmp_path / "progress.log"
    progress = ObservedProgress(path, interval_seconds=0.01)
    before = set(threading.enumerate())
    with progress.activity("Modell laden"):
        assert heartbeat.wait(2), "No status was emitted during the active operation"
        # The status is already flushed to the file before the activity completes.
        assert "läuft weiter" in path.read_text(encoding="utf-8")
        assert "fertig nach" not in path.read_text(encoding="utf-8")
    assert not [t for t in threading.enumerate() if t not in before and t.name == "participant-bench-progress"]
    log = path.read_text(encoding="utf-8")
    assert "UTC" in log and "fertig nach" in log
    assert log == capsys.readouterr().out


def test_failure_reports_abort_and_preserves_the_original_exception(tmp_path):
    path = tmp_path / "progress.log"
    progress = Progress(path)
    with pytest.raises(ValueError, match="invalid input"):
        with progress.activity("Seite auswerten"):
            raise ValueError("invalid input")
    log = path.read_text(encoding="utf-8")
    assert "abgebrochen" in log and "ValueError: invalid input" in log
    assert "fertig nach" not in log


def test_status_can_be_disabled_and_existing_log_is_appended(tmp_path, capsys):
    path = tmp_path / "progress.log"
    disabled = Progress(path, enabled=False)
    with disabled.activity("unsichtbar"):
        disabled.log("ebenfalls unsichtbar")
    assert not path.exists()
    assert capsys.readouterr().out == ""
    Progress(path).log("erster Lauf")
    Progress(path).log("fortgesetzter Lauf")
    log = path.read_text(encoding="utf-8")
    assert "erster Lauf" in log and "fortgesetzter Lauf" in log


def test_weight_verification_reports_actual_files_and_errors(tmp_path, capsys):
    # Test file-verification status only; these are not executable model weights.
    spec = load_config(Path("configs/local.yaml")).models["vlm"]
    spec.path = str(tmp_path)
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"synthetic verification fixture")
    write_json(tmp_path / "download_manifest.json", {
        "repo": spec.repo, "revision": spec.revision, "sha256": {weights.name: file_hash(weights)},
    })
    identity = local_model_identity(spec, verify=True, progress=Progress())
    assert identity["repo"] == spec.repo
    assert "Gewichtsprüfung [1/1]: model.safetensors" in capsys.readouterr().out
    weights.write_bytes(b"changed")
    with pytest.raises(Unavailable):
        local_model_identity(spec, verify=True, progress=Progress())


def test_pdf_preparation_reports_all_input_pages_without_selection(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), "Synthetische Teilnehmerliste")
        document.new_page()
        document.save(raw / "123456.pdf")
    config = load_config(Path("configs/smoke.yaml"))
    log_path = tmp_path / "progress.log"
    manifest = prepare(raw, config, tmp_path / "prepared", progress=Progress(log_path))
    log = log_path.read_text(encoding="utf-8")
    assert "PDF [1/1]: 123456.pdf öffnen" in log
    assert "Seite 1/2" in log and "Seite 2/2" in log
    assert "ausgeschlossen" not in log and "alle für die Extraktion enthalten" in log
    assert "OCR für Seitenauswahl" not in log
    assert manifest["pages"][0]["include"] is True
    assert manifest["pages"][1]["include"] is True
    assert log == capsys.readouterr().out
