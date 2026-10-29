"""API integration uses a loopback server and synthetic data, never a real service."""

import base64
import io
import json
import threading
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
import yaml
from participant_bench.config import Config, ModelConfig
from participant_bench.io import file_hash, read_json, read_jsonl
from participant_bench.models import Unavailable, create_model
from participant_bench.runner import run
from participant_bench.schema import SignatureResponse
from participant_bench.signature_review import recheck_run
from PIL import Image
from pydantic import ValidationError

from participant_api.backend import enable
from participant_api.cli import main
from participant_api.config import APIConfig, load_config
from participant_api.models import (
    APIConnection,
    APIModel,
    api_identity,
    checked_url,
    missing_environment,
)


@pytest.fixture(autouse=True)
def activate_api():
    enable()


KEY, CLIENT, SECRET, TOKEN = "fake-key-52a", "fake-client-93b", "fake-secret-18c", "fake-token-72d"
PERSON = {"first_name": "Anna", "last_name": "Weber", "personnel_number": "00123", "department": "MUC"}


@pytest.fixture
def service(monkeypatch):
    state = SimpleNamespace(requests=[], status=200, finish_reason="stop", custom=None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            state.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
            if self.path == "/token":
                data = {"access_token": TOKEN, "token_type": "Bearer", "expires_in": 300}
            elif self.path == "/v1/models":
                data = {"data": [{"id": "synthetic-vision"}, {"id": "synthetic-text"}]}
            else:
                payload = json.loads(body)
                schema = payload["messages"][0]["content"]
                if "SignatureLocations" in schema:
                    result = {"rows": [{"output_index": 0, "row_y": [350, 430]}]}
                elif "SignatureResponse" in schema:
                    result = {
                        "field_located": True,
                        "signature_present": True,
                        "evidence": "handwritten_mark",
                    }
                else:
                    result = {"participants": [PERSON | {"signature_present": None}], "page_text": None}
                    if "VisualCellPageResponse" in schema:
                        result = dict(name_order=dict(order="given_family", evidence="First Name | Last Name"),
                            identity_headers=["First Name", "Last Name", "User ID", "Organization"], page_text=None,
                            participants=[dict(first_name="Anna", last_name="Weber", signature_present=None,
                                identity_cells=["Anna", "Weber", "00123", "MUC"])])
                data = (
                    state.custom
                    if state.custom is not None
                    else {
                        "choices": [
                            {"message": {"content": json.dumps(result)}, "finish_reason": state.finish_reason}
                        ],
                        "model": "synthetic-vision",
                        "usage": {"prompt_tokens": 40, "completion_tokens": 25},
                    }
                )
            self.send_response(state.status)
            if state.status == 302:
                self.send_header("Location", state.url + "/redirect-target")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    for name, value in {
        "TEST_API_KEY": KEY,
        "TEST_CLIENT_ID": CLIENT,
        "TEST_CLIENT_SECRET": SECRET,
        "TEST_SCOPE": "synthetic.read",
        "TEST_RESOURCE": "synthetic-resource",
    }.items():
        monkeypatch.setenv(name, value)
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def api_spec(service, **updates):
    api = {"base_url": service.url + "/v1", "model": "synthetic-vision", "api_key_env": "TEST_API_KEY"}
    api.update(updates)
    return ModelConfig(backend="api", options=APIConfig(**api).model_dump())


def oauth_spec(service, **updates):
    values = {
        "auth": "oauth2",
        "token_url": service.url + "/token",
        "client_id_env": "TEST_CLIENT_ID",
        "client_secret_env": "TEST_CLIENT_SECRET",
        "api_key_header": "X-Gateway-Key",
        "api_key_prefix": "",
        "scope_env": "TEST_SCOPE",
        "resource_env": "TEST_RESOURCE",
    }
    values.update(updates)
    return api_spec(service, **values)


@pytest.mark.parametrize(
    ("configured", "available"),
    [("BMW_AI_CA_BUNDLE", "BMW_CA_BUNDLE"), ("BMW_CA_BUNDLE", "BMW_AI_CA_BUNDLE")],
)
def test_company_ca_variable_alias_is_used_without_network(service, monkeypatch, configured, available):
    import ssl

    for name in ("BMW_AI_CA_BUNDLE", "BMW_CA_BUNDLE"):
        monkeypatch.delenv(name, raising=False)
    synthetic_path = "synthetic-company-ca.pem"
    monkeypatch.setenv(available, synthetic_path)
    context = ssl.create_default_context()
    loaded = []

    def create_context(*, cafile):
        loaded.append(cafile)
        return context

    monkeypatch.setattr("participant_api.models.ssl.create_default_context", create_context)
    connection = APIConnection(api_spec(service, ca_bundle_env=configured))
    assert loaded == [synthetic_path]
    assert connection.token_requests == connection.inference_requests == 0
    assert service.requests == []


def test_explicit_company_ca_variable_takes_precedence(service, monkeypatch):
    import ssl

    monkeypatch.setenv("BMW_AI_CA_BUNDLE", "preferred.pem")
    monkeypatch.setenv("BMW_CA_BUNDLE", "alternative.pem")
    context = ssl.create_default_context()
    loaded = []
    monkeypatch.setattr(
        "participant_api.models.ssl.create_default_context",
        lambda *, cafile: loaded.append(cafile) or context,
    )
    APIConnection(api_spec(service, ca_bundle_env="BMW_AI_CA_BUNDLE"))
    assert loaded == ["preferred.pem"]
    assert service.requests == []


def test_api_and_local_require_their_own_configuration(tmp_path):
    with pytest.raises(ValidationError):
        ModelConfig()
    with pytest.raises(ValidationError):
        ModelConfig(backend="api")
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "methods": ["vlm"],
                "models": {
                    "vlm": {
                        "backend": "api",
                        "options": {
                            "base_url": "https://example.invalid/v1",
                            "model": "test",
                            "client_secret": SECRET,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as error:
        load_config(path)
    assert SECRET not in str(error.value) and "client_secret" in str(error.value)
    assert load_config(Path("../configs/local.yaml")).models["vlm"].backend == "local"
    assert load_config(Path("configs/api-bmw.yaml")).models["vlm"].backend == "api"


@pytest.mark.parametrize(
    "url",
    [
        "http://service.invalid/v1",
        "https://user:password@service.invalid",
        "https://service.invalid?key=secret",
        "https://service.invalid/#secret",
    ],
)
def test_unsafe_addresses_are_rejected_without_echoing_them(url):
    with pytest.raises(Unavailable) as error:
        checked_url(url)
    assert url not in str(error.value)


def test_key_auth_and_diagnostics_never_put_credentials_in_body_or_identity(service):
    spec = api_spec(service)
    connection = APIConnection(spec)
    assert connection.list_models() == ["synthetic-vision", "synthetic-text"]
    request = service.requests[0]
    assert request["headers"]["Authorization"] == "Bearer " + KEY
    assert KEY not in request["body"] and KEY not in json.dumps(api_identity(spec))
    connection.close()
    assert connection._key is None and not connection._secrets


@pytest.mark.parametrize("method", ["body", "basic"])
def test_oauth_flow_token_reuse_and_expiry(service, method):
    connection = APIConnection(oauth_spec(service, token_auth_method=method))
    connection.list_models()
    connection.list_models()
    assert [row["path"] for row in service.requests] == ["/token", "/v1/models", "/v1/models"]
    token_request, model_request = service.requests[:2]
    form = urllib.parse.parse_qs(token_request["body"])
    assert form["grant_type"] == ["client_credentials"] and form["scope"] == ["synthetic.read"]
    assert form["resource"] == ["synthetic-resource"]
    if method == "body":
        assert form["client_id"] == [CLIENT] and form["client_secret"] == [SECRET]
    else:
        expected = base64.b64encode(f"{CLIENT}:{SECRET}".encode()).decode()
        assert token_request["headers"]["Authorization"] == "Basic " + expected
        assert connection.redact(expected) == "[REDACTED]"
        assert "client_secret" not in form
    assert "X-Gateway-Key" not in token_request["headers"]
    assert model_request["headers"]["Authorization"] == "Bearer " + TOKEN
    assert model_request["headers"]["X-Gateway-Key"] == KEY
    assert SECRET not in json.dumps(model_request)
    connection._expires = 0
    connection.list_models()
    assert connection.token_requests == 2
    assert connection.redact(" ".join((KEY, CLIENT, SECRET, TOKEN))) == " ".join(["[REDACTED]"] * 4)


def test_token_endpoint_only_receives_api_key_when_configured(service):
    connection = APIConnection(oauth_spec(service, token_send_api_key=True))
    connection.list_models()
    assert service.requests[0]["headers"]["X-Gateway-Key"] == KEY
    with pytest.raises(Unavailable, match="Header"):
        APIConnection(oauth_spec(service, api_key_header="Authorization"))


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_http_failure_is_sanitized_no_redirect_or_automatic_retry(service, status):
    service.status, service.custom = status, {"error": SECRET + KEY}
    connection = APIConnection(api_spec(service))
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as error:
        connection.chat({"messages": [{"content": "synthetic"}]})
    assert KEY not in str(error.value) and SECRET not in str(error.value)
    assert len(service.requests) == 1


def test_timeout_is_sanitized(service, monkeypatch):
    connection = APIConnection(api_spec(service))

    def fail(*args, **kwargs):
        raise urllib.error.URLError(KEY + SECRET)

    monkeypatch.setattr(connection.opener, "open", fail)
    with pytest.raises(RuntimeError) as error:
        connection.list_models()
    assert KEY not in str(error.value) and SECRET not in str(error.value)


def test_missing_environment_and_offline_fail_before_reading_pdfs(service, monkeypatch, tmp_path):
    config = Config(methods=["vlm"], models={"vlm": api_spec(service)}, output_dir=str(tmp_path / "runs"))
    with pytest.raises(ValueError, match="offline"):
        run(config, tmp_path / "nonexistent", offline=True)
    monkeypatch.setenv("TEST_API_KEY", "   ")
    assert missing_environment(config.models["vlm"]) == ["TEST_API_KEY"]
    with pytest.raises(Unavailable, match="TEST_API_KEY"):
        run(config, tmp_path / "nonexistent")
    assert not (tmp_path / "runs").exists() and not service.requests


def test_api_factory_image_schema_and_usage_without_loading_local_weights(service):
    spec = api_spec(service, response_format="json_schema", max_tokens_parameter="max_completion_tokens")
    spec.max_pixels = 65536
    config = Config(methods=["vlm"], models={"vlm": spec})

    def no_local(*args, **kwargs):
        raise AssertionError("API attempted local model initialization")

    model = create_model("vlm", config, local_class=no_local)
    assert isinstance(model, APIModel)
    with Image.new("RGB", (800, 600), "white") as image:
        raw, metadata = model.generate(
            "synthetic", image, response_type=SignatureResponse, system_prompt="test"
        )
    request = json.loads(service.requests[0]["body"])
    assert request["response_format"]["json_schema"]["name"] == "SignatureResponse"
    assert request["max_completion_tokens"] == spec.max_new_tokens and "temperature" not in request
    data_url = request["messages"][1]["content"][1]["image_url"]["url"]
    with Image.open(io.BytesIO(base64.b64decode(data_url.split(",")[1]))) as image:
        assert image.width * image.height <= spec.max_pixels + image.width + image.height
    assert metadata["input_tokens"] == 40 and metadata["output_tokens"] == 25
    assert model.resources()["peak_gpu_allocated_bytes"] is None
    assert KEY not in raw


def test_api_vlm_uses_physical_cells_and_preserves_an_empty_employee_id(service):
    result = {
        "identity_headers": ["Benutzername", "Benutzer", "Kurzzeichen"],
        "participants": [{"row_ref": "1", "first_name": "Anna", "last_name": "Weber",
                          "identity_cells": ["Weber, Anna", "", "AB 123"], "signature_present": None}],
        "page_text": None,
    }
    service.custom = {"choices": [{"message": {"content": json.dumps(result)}, "finish_reason": "stop"}]}
    spec = oauth_spec(service, response_format="json_schema")
    model = APIModel("vlm", Config(methods=["vlm"], models={"vlm": spec}))
    try:
        with Image.new("RGB", (256, 256), "white") as image:
            people, records, status, _ = model.extract(image)
        assert status == "success" and len(people) == 1
        assert people[0].personnel_number.value == "" and people[0].personnel_number.state == "empty"
        assert people[0].department.value == "AB 123"
        assert records[0]["identity_column_assignment"]["field_columns"] == {
            "personnel_number": 1, "department": 2,
        }
        assert service.requests[0]["path"] == "/token"
        request = json.loads(service.requests[-1]["body"])
        assert request["response_format"]["json_schema"]["name"] == "VisualCellPageResponse"
        assert model.calls == 1
    finally:
        model.close()


def test_text_api_preserves_ocr_grounding_contract_and_rejects_unobserved_fields(service):
    model = APIModel("ocr_llm", Config(methods=["ocr_llm"], models={"ocr_llm": api_spec(service)}))
    service.custom = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "participants": [
                                PERSON | {"first_name": "Invented", "word_ids": [0, 1, 2, 3]},
                            ]
                        }
                    )
                }
            }
        ]
    }
    ocr = {
        "words": [
            {
                "text": value,
                "bbox": {"x0": index / 5, "y0": 0.3, "x1": index / 5 + 0.1, "y1": 0.32},
                "ocr_confidence": 90,
                "line": [1, 1, 1],
            }
            for index, value in enumerate(PERSON.values())
        ]
    }
    ocr["text"] = " ".join(PERSON.values())
    with Image.new("RGB", (500, 500), "white") as image:
        people, records, _, _ = model.extract(image, ocr)
    assert len(people) == 1 and people[0].personnel_number.value == "00123", records[0].get("error")
    assert people[0].first_name.value is None and people[0].last_name.value == "Weber"
    assert records[0]["input_tokens"] is None and records[0]["output_tokens"] is None
    content = json.loads(service.requests[0]["body"])["messages"][1]["content"]
    assert len(content) == 1 and content[0]["type"] == "text" and "Anna" in content[0]["text"]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": None}}]},
        {"choices": [{"message": {"refusal": "synthetic refusal"}}]},
    ],
)
def test_malformed_and_refused_responses_are_errors(service, response):
    service.custom = response
    model = APIModel("vlm", Config(methods=["vlm"], models={"vlm": api_spec(service)}))
    with pytest.raises(RuntimeError):
        model.generate("synthetic")


def test_truncated_output_is_not_silently_accepted_and_credentials_are_redacted(service):
    service.finish_reason = "length"
    model = APIModel("vlm", Config(methods=["vlm"], models={"vlm": api_spec(service)}))
    with Image.new("RGB", (100, 100)) as image:
        people, records, _, _ = model.extract(image)
    assert not people and records[0]["error_stage"] == "output_budget"
    service.custom = {"choices": [{"message": {"content": KEY + SECRET}}]}
    model = APIModel("vlm", Config(methods=["vlm"], models={"vlm": oauth_spec(service)}))
    raw, _ = model.generate("synthetic")
    assert raw == "[REDACTED][REDACTED]"


def test_synthetic_pdf_api_signature_export_resume_and_recheck(service, tmp_path, monkeypatch):
    config = Config(
        methods=["vlm"],
        models={"vlm": oauth_spec(service)},
        output_dir=str(tmp_path / "runs"),
        cache_dir=str(tmp_path / "cache"),
    )
    config.pdf.auto_orient = False
    config.signature.backend = "vlm"
    config.signature.use_ocr_positions = False
    raw = tmp_path / "pdfs"
    raw.mkdir()
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((80, 300), "Anna Weber 00123 MUC")
        document.save(raw / "123456.pdf")
    original = file_hash(raw / "123456.pdf")
    monkeypatch.setattr("participant_bench.runner.environment", lambda *args: {})
    output, summary = run(config, raw)
    assert summary["vlm"]["status"] == "success" and summary["vlm"]["model_backend"] == "api"
    people = read_jsonl(output / "vlm/extractions.jsonl")[0]["participants"]
    assert len(people) == 1 and people[0]["first_name"]["value"] == "Anna"
    assert people[0]["signature_present"] is True and people[0]["signature_method"] == "api_vlm_detail"
    assert read_json(output / "vlm/resources.json")["http_model_requests"] == 3
    assert (output / "report.html").is_file()
    assert "Modell-Backend" in (output / "report.html").read_text(encoding="utf-8")
    calls = len(service.requests)
    _, summary = run(config, raw, resume=output)
    assert summary["vlm"]["resume_reused_pages"] == 1 and len(service.requests) == calls
    rechecked = recheck_run(output, config, output=tmp_path / "recheck")
    assert len(service.requests) == calls + 2  # Initial decision changed; one fresh token and detail request.
    assert (
        read_jsonl(rechecked / "vlm/extractions.jsonl")[0]["participants"][0]["first_name"]
        == people[0]["first_name"]
    )
    calls = len(service.requests)
    recheck_run(output, config, output=tmp_path / "recheck-cached")
    assert len(service.requests) == calls
    for folder in (output, tmp_path / "cache"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in (
                ".json",
                ".jsonl",
                ".yaml",
                ".log",
                ".html",
                ".csv",
                ".txt",
            ):
                text = path.read_text(encoding="utf-8-sig")
                assert all(secret not in text for secret in (KEY, CLIENT, SECRET, TOKEN)), path
    assert file_hash(raw / "123456.pdf") == original


def test_api_check_default_is_read_only_and_connect_lists_models_without_inference(
    service, tmp_path, monkeypatch, capsys
):
    config = Config(methods=["vlm"], models={"vlm": oauth_spec(service)})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["participant-bench", "api-check", "--config", str(path)])
    assert main() == 0 and not service.requests
    assert KEY not in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["participant-bench", "api-check", "--config", str(path), "--connect"])
    assert main() == 0
    assert [row["path"] for row in service.requests] == ["/token", "/v1/models"]
    assert "synthetic-vision" in capsys.readouterr().out


def test_api_check_reports_authentication_failure_without_leaking_credentials(
    service, tmp_path, monkeypatch, capsys
):
    config = Config(methods=["vlm"], models={"vlm": oauth_spec(service)})
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    service.status = 401
    monkeypatch.setattr("sys.argv", ["participant-bench", "api-check", "--config", str(path), "--connect"])
    assert main() == 1
    report = capsys.readouterr().out
    assert "HTTP 401" in report and all(value not in report for value in (KEY, CLIENT, SECRET, TOKEN))
    assert len(service.requests) == 1


def test_main_smoke_requests_basic_oauth_before_the_model(service, tmp_path, capsys):
    config = Config(
        methods=["ocr_llm"],
        models={"ocr_llm": oauth_spec(service, token_auth_method="basic")},
    )
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    service.custom = {"choices": [{"message": {"content": "OK"}}]}
    assert main(["smoke", "--config", str(path), "--method", "ocr_llm"]) == 0
    assert [request["path"] for request in service.requests] == ["/token", "/v1/chat/completions"]
    token, model = service.requests
    assert token["headers"]["Authorization"].startswith("Basic ")
    assert model["headers"]["Authorization"] == "Bearer " + TOKEN
    assert model["headers"]["X-Gateway-Key"] == KEY
    assert json.loads(model["body"])["messages"] == [{"role": "user", "content": "Reply with OK."}]
    output = capsys.readouterr()
    assert "OK" in output.out
    assert all(value not in output.out + output.err for value in (KEY, CLIENT, SECRET, TOKEN))


def test_main_smoke_missing_credentials_fails_without_network(service, monkeypatch, tmp_path, capsys):
    config = Config(methods=["ocr_llm"], models={"ocr_llm": oauth_spec(service)})
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()), encoding="utf-8")
    monkeypatch.delenv("TEST_CLIENT_SECRET")
    assert main(["smoke", "--config", str(path)]) == 1
    assert not service.requests
    output = capsys.readouterr()
    assert "TEST_CLIENT_SECRET" in output.err
    assert all(value not in output.out + output.err for value in (KEY, CLIENT, SECRET, TOKEN))


@pytest.mark.parametrize("extension", ["csv", "xlsx"])
def test_api_framework_runs_multiple_pdfs_and_scores_locally_without_sending_reference(
    service, tmp_path, monkeypatch, capsys, extension
):
    from openpyxl import Workbook

    inputs = tmp_path / "pdfs"
    inputs.mkdir()
    for course in ("123456", "654321"):
        with pymupdf.open() as document:
            document.new_page().insert_text((30, 70), f"Synthetic document {course}: Anma Weber")
            document.save(inputs / f"{course}.pdf")
    reference = tmp_path / f"reference.{extension}"
    rows = [
        ["Class ID", "User ID", "First Name", "Last Name", "Organization"],
        ["654321", "000007", "Anna", "Weber", "MUC"],
        ["999999", "000009", "REFERENCE_EXCLUSIVE_NEVER_SENT_TO_API", "Other", "REF"],
        ["123456", "000007", "Anna", "Weber", "MUC"],
    ]
    if extension == "csv":
        reference.write_text("\n".join(";".join(row) for row in rows), encoding="utf-8")
    else:
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(reference)
        book.close()
    originals = {path: file_hash(path) for path in [reference, *inputs.glob("*.pdf")]}
    extraction = Config(methods=["vlm"], models={"vlm": oauth_spec(service)},
                        output_dir=str(tmp_path / "extractions"), cache_dir=str(tmp_path / "cache"))
    extraction.pdf.auto_orient = False
    model_config = tmp_path / "models.yaml"
    model_config.write_text(yaml.safe_dump(extraction.model_dump()), encoding="utf-8")
    benchmark_config = tmp_path / "benchmark.yaml"
    benchmark_config.write_text(yaml.safe_dump(dict(input_dir="pdfs", reference_file=reference.name,
                                                    extraction_config="models.yaml", output_dir="results",
                                                    matching={"mode": "best_fit"})),
                                encoding="utf-8")
    response = dict(identity_headers=["Benutzername", "Benutzer", "Kurzzeichen"], participants=[dict(
        row_ref="1", first_name="Weber", last_name="Anma", identity_cells=["Weber, Anma", "000007", "MUC"],
        signature_present=None)], page_text=None)
    response["name_order"] = dict(order="family_given", evidence="Benutzername: Nachname, Vorname")
    response["participants"].append(dict(first_name="Max", last_name="Muster", identity_cells=["Muster, Max", "", "MUC"],
                                         person_role="instructor", role_evidence="Kursleiter"))
    service.custom = {"choices": [{"message": {"content": json.dumps(response)}, "finish_reason": "stop"}]}
    monkeypatch.setattr("participant_bench.runner.environment", lambda *args: {})
    assert main(["benchmark", "run", "--config", str(benchmark_config)]) == 0
    output = next((tmp_path / "results").iterdir())
    metrics = read_json(output / "metrics.json")
    assert metrics["scope"]["input_pdfs"] == 2 and metrics["scope"]["courses_compared"] == 2
    assert metrics["scope"]["reference_rows_outside_input"] == 1
    assert metrics["methods"]["vlm"]["score_percent"] == 93.75
    assert metrics["methods"]["vlm"]["matching_mode"] == "best_fit"
    assert metrics["methods"]["vlm"]["conservative_score_percent"] == 93.75
    assert metrics["methods"]["vlm"]["reference_participants"] == 2
    assert metrics["methods"]["vlm"]["excluded_instructors"] == 2
    assert (output / "report.html").is_file() and (output / "participants.xlsx").is_file()
    assert (output / "details.html").is_file()
    assert (output / "zuordnungen.html").is_file()
    assert read_json(output / "details/calculation_checks.json")["vlm"]["contributions_match_saved_metrics"]
    assert [request["path"] for request in service.requests] == ["/token", "/v1/chat/completions", "/v1/chat/completions"]
    assert all("REFERENCE_EXCLUSIVE_NEVER_SENT_TO_API" not in request["body"] for request in service.requests)
    assert all(file_hash(path) == expected for path, expected in originals.items())
    console = capsys.readouterr()
    assert "93.75%" in console.out and "REFERENCE_EXCLUSIVE" not in console.out
    assert all(secret not in console.out + console.err for secret in (KEY, CLIENT, SECRET, TOKEN))
    source = read_json(output / "identity.json")["source_run"]
    source_pages = read_jsonl(Path(source) / "vlm/extractions.jsonl")
    assert all(len(page["participants"]) == len(page["excluded_instructors"]) == 1 for page in source_pages)
    calls = len(service.requests)
    for name in ("TEST_API_KEY", "TEST_CLIENT_ID", "TEST_CLIENT_SECRET"):
        monkeypatch.delenv(name)
    assert main(["benchmark", "compare", "--config", str(benchmark_config),
                 "--run", source, "--output", str(tmp_path / "comparison")]) == 0
    assert len(service.requests) == calls
    assert read_json(tmp_path / "comparison/metrics.json")["methods"]["vlm"]["score_percent"] == 93.75
    assert main(["benchmark", "details", "--report", str(tmp_path / "comparison")]) == 0
    assert main(["benchmark", "assignments", "--report", str(tmp_path / "comparison")]) == 0
    assert len(service.requests) == calls


def test_api_framework_check_requires_no_credentials_or_model_requests(service, tmp_path, monkeypatch, capsys):
    inputs = tmp_path / "pdfs"
    inputs.mkdir()
    with pymupdf.open() as document:
        document.new_page().insert_text((30, 70), "Synthetic document")
        document.save(inputs / "123456.pdf")
    (tmp_path / "reference.csv").write_text(
        "Class ID;First Name;Last Name;Organization\n123456;Anna;Weber;MUC\n", encoding="utf-8")
    config = tmp_path / "benchmark.yaml"
    config.write_text("input_dir: pdfs\nreference_file: reference.csv\n", encoding="utf-8")
    for name in ("TEST_API_KEY", "TEST_CLIENT_ID", "TEST_CLIENT_SECRET"):
        monkeypatch.delenv(name)
    assert main(["benchmark", "check", "--config", str(config)]) == 0
    assert not service.requests
    message = json.loads(capsys.readouterr().out)
    assert message["input_pdfs"] == 1 and not message["network_contacted"]
