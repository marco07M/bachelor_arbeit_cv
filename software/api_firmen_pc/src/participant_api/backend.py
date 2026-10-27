"""Explicit integration with the shared, locally usable analysis code."""

from participant_bench.models import Unavailable, register_model_backend

from .config import connection_config
from .models import APIModel, api_identity, checked_url, env_value, missing_environment


def validate(spec):
    missing = missing_environment(spec)
    if missing:
        raise Unavailable("Umgebungsvariablen fehlen: " + ", ".join(missing) + "; main.py check verwenden")
    api_identity(spec)
    api = connection_config(spec)
    if api.auth == "oauth2":
        checked_url(env_value(api.token_url_env, api.token_url))


def enable():
    register_model_backend("api", factory=APIModel, identity=api_identity, validate=validate)
