"""Dedicated entry point, independent of private example files and real credentials."""

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

from participant_api.cli import main


def test_help_does_not_read_configuration_or_contact_service(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Help must not load credentials or contact a server")

    monkeypatch.setattr("participant_api.cli.load_config", forbidden)
    assert main(["--help"]) == 0
    assert "Firmen-PC" in capsys.readouterr().out


def test_company_environment_does_not_need_gpu_packages():
    # This is a genuinely separate uv environment installed without the models extra.
    assert importlib.util.find_spec("torch") is None
    assert importlib.util.find_spec("transformers") is None
    assert not {"torch", "transformers"} & set(sys.modules)


def test_default_config_uses_main_sequence_without_ocr():
    from participant_api.cli import DEFAULT_CONFIG
    from participant_api.config import connection_config, load_config

    config = load_config(DEFAULT_CONFIG)
    assert config.methods == ["vlm"] and not config.pdf.auto_orient
    assert not config.signature.use_ocr_positions
    for model in config.models.values():
        options = connection_config(model)
        assert options.auth == "oauth2" and options.token_auth_method == "basic"
        assert options.api_key_header == "x-apikey"
        assert options.client_id_env == "BMW_AI_CLIENT_ID"


def test_export_contains_shared_sources_but_no_private_data(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "export_company_bundle.py"
    spec = importlib.util.spec_from_file_location("company_bundle", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = module.build_bundle(tmp_path / "company.zip")
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "software/api_firmen_pc/main.py" in names
    assert "software/verarbeitung/src/participant_bench/runner.py" in names
    assert "software/api_firmen_pc/uv.lock" in names
    assert "software/api_firmen_pc/certificates/BMW_Trusted_Certificates_Latest.pem" in names
    assert "software/api_firmen_pc/docs/gate-zugang.md" in names
    assert not any(
        name.endswith(".pdf") or {"privat", ".venv", "models", "runs", ".cache"} & set(Path(name).parts)
        for name in names
    )
    with pytest.raises(FileExistsError):
        module.build_bundle(output)
