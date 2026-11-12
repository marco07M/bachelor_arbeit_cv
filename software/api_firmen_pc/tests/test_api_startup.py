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
    local_config = load_config(Path("../configs/vlm-comparison.yaml"))
    assert config.methods == local_config.methods == ["vlm"]
    assert config.pdf.model_dump() == local_config.pdf.model_dump()
    assert config.signature.model_dump(exclude={"backend"}) == local_config.signature.model_dump(
        exclude={"backend"}
    )
    assert config.signature.backend == "vlm"
    assert local_config.signature.backend == "local_vlm"
    assert config.models["vlm"].max_pixels == local_config.models["vlm"].max_pixels
    assert config.models["vlm"].max_new_tokens == local_config.models["vlm"].max_new_tokens
    api_options = connection_config(config.models["vlm"])
    assert api_options.model_env == "BMW_VLM_MODEL"
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
    assert "software/verarbeitung/src/participant_bench/vlm_cells.py" in names
    assert "software/verarbeitung/src/participant_bench/person_roles.py" in names
    assert "software/verarbeitung/src/participant_bench/document_names.py" in names
    assert "software/verarbeitung/src/participant_bench/roster_benchmark/detail_report.py" in names
    assert "software/verarbeitung/src/participant_bench/roster_benchmark/assignment_report.py" in names
    assert "software/api_firmen_pc/start_api_testframework.cmd" in names
    assert "software/api_firmen_pc/testframework/main.py" in names
    assert "software/api_firmen_pc/testframework/config.yaml" in names
    assert "software/testframework/config.yaml" in names
    assert "software/api_firmen_pc/testframework/referenz/README.md" in names
    assert "software/api_firmen_pc/uv.lock" in names
    assert "software/api_firmen_pc/certificates/BMW_Trusted_Certificates_Latest.pem" in names
    assert "software/api_firmen_pc/docs/gate-zugang.md" in names
    assert "software/configs/vlm-comparison.yaml" in names
    assert not any(
        name.endswith(".pdf") or {"privat", ".venv", "models", "runs", ".cache"} & set(Path(name).parts)
        for name in names
    )
    with pytest.raises(FileExistsError):
        module.build_bundle(output)


def test_api_framework_uses_api_vlm_and_same_matching_settings_as_local():
    from participant_bench.roster_benchmark.config import load_config as load_benchmark

    from participant_api.benchmark import DEFAULT_CONFIG
    from participant_api.config import load_config

    config = load_benchmark(DEFAULT_CONFIG)
    local = load_benchmark(Path("../testframework/config.yaml"))
    assert config.matching == local.matching and config.reference == local.reference
    extraction = load_config(DEFAULT_CONFIG.parent / config.extraction_config)
    assert extraction.methods == ["vlm"] and not extraction.pdf.auto_orient
    assert extraction.models["vlm"].backend == "api"
    assert not config.signature_detail_checks


def test_api_ocr_profile_has_separate_configured_remote_llm_and_vlm():
    from participant_api.config import connection_config, load_config

    config = load_config(Path("configs/api-ocr.yaml"))
    assert config.models["ocr_llm"].backend == config.models["vlm"].backend == "api"
    assert connection_config(config.models["ocr_llm"]).model_env == "BMW_LLM_MODEL"
    assert connection_config(config.models["vlm"]).model_env == "BMW_VLM_MODEL"
