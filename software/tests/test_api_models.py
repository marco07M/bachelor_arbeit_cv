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
from participant_bench.api_models import (
    APIConnection,
    APIModel,
    api_identity,
    checked_url,
    missing_environment,
)
from participant_bench.cli import main
from participant_bench.config import APIConfig, Config, ModelConfig, load_config
from participant_bench.io import file_hash, read_json, read_jsonl
from participant_bench.models import Unavailable, create_model
from participant_bench.runner import run
from participant_bench.schema import SignatureResponse
from participant_bench.signature_review import recheck_run
from PIL import Image
from pydantic import ValidationError

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
    return ModelConfig(backend="api", api=APIConfig(**api))


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
                        "api": {
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
    assert load_config(Path("configs/local.yaml")).models["vlm"].backend == "local"
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
