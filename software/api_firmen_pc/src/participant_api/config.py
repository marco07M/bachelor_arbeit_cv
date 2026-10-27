"""Connection settings used only on the company PC; fields contain environment names."""

from pathlib import Path
from typing import Literal

from participant_bench.config import ConfigModel
from participant_bench.config import load_config as load_core_config
from pydantic import Field, ValidationError, model_validator


class APIConfig(ConfigModel):
    # These are environment-variable names, never credential values.
    base_url: str | None = None
    base_url_env: str | None = None
    model: str | None = None
    model_env: str | None = None
    chat_path: str = "chat/completions"
    chat_path_env: str | None = None
    api_version: str | None = None
    auth: Literal["api_key", "oauth2"] = "api_key"
    api_key_env: str | None = "API_KEY"
    api_key_header: str = "Authorization"
    api_key_header_env: str | None = None
    api_key_prefix: str = "Bearer "
    token_url: str | None = None
    token_url_env: str | None = None
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"
    scope_env: str | None = None
    resource_env: str | None = None
    token_auth_method: Literal["body", "basic"] = "body"
    token_send_api_key: bool = False
    ca_bundle_env: str | None = None
    timeout_seconds: float = Field(default=120, gt=0, le=1800)
    response_format: Literal["json_object", "json_schema", "none"] = "json_object"
    max_tokens_parameter: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    image_detail: Literal["auto", "high", "low"] = "high"
    send_temperature: bool = False

    @model_validator(mode="after")
    def configured(self):
        if not self.base_url and not self.base_url_env:
            raise ValueError("API benötigt base_url oder base_url_env")
        if not self.model and not self.model_env:
            raise ValueError("API benötigt model oder model_env")
        if self.auth == "oauth2" and not self.token_url and not self.token_url_env:
            raise ValueError("OAuth benötigt token_url oder token_url_env")
        if self.auth == "api_key" and not self.api_key_env:
            raise ValueError("API-Key-Anmeldung benötigt api_key_env")
        return self


def connection_config(spec) -> APIConfig:
    try:
        return APIConfig.model_validate(spec.options)
    except ValidationError as exc:
        locations = [".".join(map(str, item["loc"])) for item in exc.errors(include_input=False)]
        raise ValueError("API-Konfiguration ungueltig; Felder pruefen: " + ", ".join(locations)) from None


def load_config(path: Path):
    config = load_core_config(path)
    for spec in config.models.values():
        if spec.backend == "api":
            connection_config(spec)
    return config
