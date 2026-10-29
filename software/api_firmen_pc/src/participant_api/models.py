"""Configurable chat API and OAuth client credentials; credentials remain in process memory."""

import base64
import io
import json
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from participant_bench.config import Config, ModelConfig
from participant_bench.models import LocalModel, Unavailable, build_system, generation_schema
from participant_bench.progress import Progress
from participant_bench.schema import OCRTextPageResponse, VisualCellPageResponse
from PIL import Image
from pydantic import BaseModel

from .config import connection_config


def env_value(name: str | None, fallback: str | None = None, required: bool = True) -> str | None:
    value = os.environ.get(name, fallback) if name else fallback
    if required and (value is None or not str(value).strip()):
        raise Unavailable(f"Umgebungsvariable {name or '(Adresse/Modell in der Konfiguration)'} fehlt")
    return value


def checked_url(value: str) -> str:
    parts = urllib.parse.urlsplit(value)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(ch.isspace() for ch in value)
        or not (parts.scheme == "https" or parts.scheme == "http" and local)
    ):
        raise Unavailable(
            "API-/Token-Adresse muss HTTPS ohne Zugangsdaten oder Query verwenden (HTTP nur Loopback)"
        )
    return value.rstrip("/")


def api_identity(spec: ModelConfig, require_model: bool = True) -> dict[str, str | None]:
    api = connection_config(spec)
    base = checked_url(env_value(api.base_url_env, api.base_url))
    model = env_value(api.model_env, api.model, required=require_model)
    path = env_value(api.chat_path_env, api.chat_path)
    if (
        urllib.parse.urlsplit(path).scheme
        or path.startswith("//")
        or ".." in path.split("/")
        or "?" in path
        or "#" in path
    ):
        raise Unavailable("chat_path muss ein relativer Anfragepfad ohne Query sein")
    return {
        "backend": "api",
        "protocol": "chat_completions",
        "base_url": base,
        "model": model,
        "chat_path": path,
        "api_version": api.api_version,
    }


def missing_environment(spec: ModelConfig, include_model: bool = True) -> list[str]:
    api = connection_config(spec)
    required = [(api.base_url_env, api.base_url), (api.chat_path_env, api.chat_path)]
    if include_model:
        required.append((api.model_env, api.model))
    if api.api_key_env:
        required.append((api.api_key_env, None))
    if api.api_key_header_env:
        required.append((api.api_key_header_env, None))
    if api.auth == "oauth2":
        required.extend(
            ((api.token_url_env, api.token_url), (api.client_id_env, None), (api.client_secret_env, None))
        )
    return list(
        dict.fromkeys(
            name or "Adresse/Modell konfigurieren"
            for name, default in required
            if not (env_value(name, default, required=False) or "").strip()
        )
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirect target.


class APIConnection:
    def __init__(
        self, spec: ModelConfig, progress: Progress | None = None, require_model: bool = True
    ) -> None:
        self.spec, self.api = spec, connection_config(spec)
        self.identity = api_identity(spec, require_model=require_model)
        self.progress = progress or Progress(enabled=False)
        missing = missing_environment(spec, include_model=require_model)
        if missing:
            raise Unavailable("API-Konfiguration: Umgebungsvariablen fehlen: " + ", ".join(missing))
        api = self.api
        self._key = env_value(api.api_key_env, required=False) if api.api_key_env else None
        self._client_id = env_value(api.client_id_env) if api.auth == "oauth2" else None
        self._client_secret = env_value(api.client_secret_env) if api.auth == "oauth2" else None
        self._token, self._expires = None, 0.0
        self._secrets = [value for value in (self._key, self._client_id, self._client_secret) if value]
        self.key_header = env_value(api.api_key_header_env, api.api_key_header)
        if (
            not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", self.key_header)
            or api.auth == "oauth2"
            and self._key
            and self.key_header.lower() == "authorization"
        ):
            raise Unavailable("API-Key benötigt einen gültigen eigenen Header; OAuth verwendet Authorization")
        self.token_url = (
            checked_url(env_value(api.token_url_env, api.token_url)) if api.auth == "oauth2" else None
        )
        ca_bundle = env_value(api.ca_bundle_env, required=False)
        # Accept the remote launcher's spelling without changing existing local configurations.
        if not ca_bundle and api.ca_bundle_env in ("BMW_AI_CA_BUNDLE", "BMW_CA_BUNDLE"):
            alternate = "BMW_CA_BUNDLE" if api.ca_bundle_env == "BMW_AI_CA_BUNDLE" else "BMW_AI_CA_BUNDLE"
            ca_bundle = env_value(alternate, required=False)
        try:
            context = ssl.create_default_context(cafile=ca_bundle or None)
        except (OSError, ssl.SSLError):
            raise Unavailable(
                "Firmen-CA konnte nicht geladen werden; konfigurierte CA-Umgebungsvariable prüfen"
            ) from None
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
        self.inference_requests = self.token_requests = 0

    def redact(self, value: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return value

    def _json(self, request: urllib.request.Request, token_request: bool = False) -> Any:
        if token_request:
            self.token_requests += 1
        else:
            self.inference_requests += 1
        try:
            with self.opener.open(request, timeout=self.api.timeout_seconds) as response:
                content = response.read(20 * 1024**2 + 1)
                if len(content) > 20 * 1024**2:
                    raise RuntimeError("API-Antwort überschreitet 20 MiB")
                return json.loads(content)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            label = "OAuth-Token" if token_request else "Modell-API"
            raise RuntimeError(
                f"{label}: HTTP {code}; Endpunkt, Berechtigungen und Anmeldung prüfen"
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError(
                "API-Verbindung fehlgeschlagen; VPN/Proxy, TLS-Zertifikat und Erreichbarkeit prüfen"
            ) from None
        except (ValueError, UnicodeError):
            raise RuntimeError("API-Antwort ist kein gültiges JSON") from None

    def _bearer(self) -> str:
        if self._token and time.monotonic() < self._expires:
            return self._token
        self.progress.log("API: OAuth-Zugriffstoken anfordern")
        form = {"grant_type": "client_credentials"}
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        if self.api.token_auth_method == "basic":
            pair = (
                urllib.parse.quote_plus(self._client_id) + ":" + urllib.parse.quote_plus(self._client_secret)
            )
            encoded_credentials = base64.b64encode(pair.encode()).decode()
            self._secrets.append(encoded_credentials)
            headers["Authorization"] = "Basic " + encoded_credentials
        else:
            form.update(client_id=self._client_id, client_secret=self._client_secret)
        for field, name in (("scope", self.api.scope_env), ("resource", self.api.resource_env)):
            value = env_value(name, required=False)
            if value:
                form[field] = value
        if self.api.token_send_api_key and self._key:
            headers[self.key_header] = self.api.api_key_prefix + self._key
        request = urllib.request.Request(
            self.token_url, data=urllib.parse.urlencode(form).encode(), headers=headers
        )
        data = self._json(request, token_request=True)
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("access_token"), str)
            or not data["access_token"]
            or not isinstance(data.get("token_type", "Bearer"), str)
            or data.get("token_type", "Bearer").casefold() != "bearer"
        ):
            raise RuntimeError("OAuth-Antwort enthält keinen verwendbaren Bearer-Zugriffstoken")
        self._token = data["access_token"]
        self._secrets.append(self._token)
        try:
            lifetime = float(data.get("expires_in", 300))
            lifetime = lifetime if math.isfinite(lifetime) else 0
        except (TypeError, ValueError):
            lifetime = 0
        self._expires = time.monotonic() + max(0, lifetime - min(30, lifetime * 0.1))
        return self._token

    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api.auth == "oauth2":
            headers["Authorization"] = "Bearer " + self._bearer()
        if self._key:
            headers[self.key_header] = self.api.api_key_prefix + self._key
        return headers

    def endpoint(self, path: str) -> str:
        path = path.replace("{model}", urllib.parse.quote(self.identity["model"] or "", safe=""))
        url = self.identity["base_url"] + "/" + path.lstrip("/")
        return (
            url + "?" + urllib.parse.urlencode({"api-version": self.api.api_version})
            if self.api.api_version
            else url
        )

    def chat(self, payload: dict[str, Any]) -> Any:
        return self._json(
            urllib.request.Request(
                self.endpoint(self.identity["chat_path"]),
                data=json.dumps(payload).encode("utf-8"),
                headers=self.headers(),
            )
        )

    def list_models(self) -> list[str]:
        data = self._json(
            urllib.request.Request(self.endpoint("models"), headers=self.headers(), method="GET")
        )
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise RuntimeError("API unterstützt keine Modellliste im erwarteten Format")
        return [
            self.redact(row["id"])
            for row in data["data"]
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ]

    def close(self) -> None:
        self._key = self._client_id = self._client_secret = self._token = None
        self._secrets.clear()


class APIModel(LocalModel):
    def __init__(self, method: str, config: Config, progress: Progress | None = None) -> None:
        started = time.perf_counter()
        self.method, self.config, self.spec = method, config, config.models[method]
        self.progress = progress or Progress(enabled=False)
        self.client = APIConnection(self.spec, self.progress)
        self.identity = self.client.identity
        self.calls = self.warmup_calls = 0
        self.load_seconds = time.perf_counter() - started
        self.warmup_seconds = 0.0
        self.progress.log(f"{method}: API-Backend bereit; Modell {self.identity['model']}")

    def generate(
        self,
        text: str,
        image: Image.Image | None = None,
        max_new_tokens: int | None = None,
        response_type: type[BaseModel] | None = None,
        system_prompt: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        response_type = response_type or (VisualCellPageResponse if self.method == "vlm" else OCRTextPageResponse)
        system = build_system(self.method, response_type, system_prompt)
        content = [{"type": "text", "text": text}]
        if image is not None:
            with image.convert("RGB") as source:
                scale = min(1.0, math.sqrt(self.spec.max_pixels / (source.width * source.height)))
                with source.resize(
                    (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
                ) as resized:
                    stream = io.BytesIO()
                    resized.save(stream, format="PNG")
                    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64," + encoded,
                        "detail": self.client.api.image_detail,
                    },
                }
            )
        payload = {
            "model": self.identity["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            self.client.api.max_tokens_parameter: max_new_tokens or self.spec.max_new_tokens,
            "stream": False,
        }
        if self.client.api.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif self.client.api.response_format == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_type.__name__,
                    "schema": generation_schema(response_type),
                    "strict": False,
                },
            }
        if self.client.api.send_temperature:
            payload["temperature"] = self.spec.temperature if self.spec.do_sample else 0
        started = time.perf_counter()
        with self.progress.activity(f"{self.method}: API-Antwort anfordern"):
            data = self.client.chat(payload)
        try:
            choice = data["choices"][0]
            if choice["message"].get("refusal"):
                raise RuntimeError("API hat die Extraktion abgelehnt")
            raw = choice["message"]["content"]
            if isinstance(raw, list):
                raw = "".join(part["text"] for part in raw if part.get("type") == "text")
            if not isinstance(raw, str):
                raise ValueError()
            usage = data.get("usage") or {}

            def numeric(value):
                return (
                    value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
                )

            metadata = {
                "generation_seconds": time.perf_counter() - started,
                "input_tokens": numeric(usage.get("prompt_tokens")),
                "output_tokens": numeric(usage.get("completion_tokens")),
                "output_budget_reached": choice.get("finish_reason") == "length",
                "backend": "api",
                "served_model": self.client.redact(str(data.get("model", self.identity["model"]))),
            }
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise RuntimeError("API-Antwort entspricht nicht dem Chat-Completions-Format") from None
        return self.client.redact(raw), metadata

    def resources(self) -> dict[str, Any]:
        return {
            "backend": "api",
            "model_identity": self.identity,
            "calls": self.calls,
            "http_model_requests": self.client.inference_requests,
            "oauth_token_requests": self.client.token_requests,
            "warmup_calls": 0,
            "load_seconds": self.load_seconds,
            "warmup_seconds": 0,
            "peak_gpu_allocated_bytes": None,
            "peak_gpu_reserved_bytes": None,
            "device_map": {"model": "api"},
            "gpu_scope": "Remote-Hardware nicht gemessen",
        }

    def close(self) -> None:
        self.client.close()
