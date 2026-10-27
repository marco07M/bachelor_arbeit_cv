"""Explicit company-PC commands; no network until check --connect, smoke or run."""

import argparse
import json
import sys
from pathlib import Path

from .backend import enable
from .config import load_config
from .models import APIConnection, api_identity, missing_environment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "api-bmw.yaml"


def check(config_path, connect=False):
    config = load_config(config_path)
    checks = {}
    for name, spec in config.models.items():
        if spec.backend != "api":
            continue
        missing = missing_environment(spec)
        checks[name] = dict(
            configured=not missing,
            missing_environment=missing,
            network_contacted=False,
            inference_verified=False,
        )
        if connect and not missing_environment(spec, include_model=False):
            connection = None
            try:
                connection = APIConnection(spec, require_model=False)
                checks[name]["network_contacted"] = True
                checks[name]["available_models"] = connection.list_models()
            except (ValueError, OSError, RuntimeError) as exc:
                checks[name]["error"] = str(exc)
            finally:
                if connection:
                    connection.close()
        elif not missing:
            checks[name]["identity"] = api_identity(spec)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks and all(c["configured"] and not c.get("error") for c in checks.values()) else 1


def smoke(config_path, method):
    config = load_config(config_path)
    if method not in config.models or config.models[method].backend != "api":
        raise ValueError("Das gewählte Verfahren benötigt eine API-Konfiguration")
    connection = APIConnection(config.models[method])
    try:
        # Token acquisition happens inside headers(), before the model request.
        response = connection.chat(
            {
                "model": connection.identity["model"],
                "messages": [{"role": "user", "content": "Reply with OK."}],
                connection.api.max_tokens_parameter: 128,
            }
        )
        try:
            text = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Modellantwort hat nicht das erwartete Chat-Completions-Format") from None
        if not isinstance(text, str):
            raise RuntimeError("Modellantwort enthält keinen Text")
        print(connection.redact(text))
        return 0
    finally:
        connection.close()


def main(argv=None):
    enable()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("check", "api-check", "smoke"):
        parser = argparse.ArgumentParser(
            description="API auf dem Firmen-PC prüfen; Zugangsdaten nur aus der Umgebung"
        )
        parser.add_argument("command", choices=["check", "api-check", "smoke"])
        parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
        parser.add_argument(
            "--connect", action="store_true", help="Token und Modellliste ohne Dokumente abrufen"
        )
        parser.add_argument("--method", choices=["ocr_llm", "vlm"], default="ocr_llm")
        args = parser.parse_args(argv)
        try:
            return (
                smoke(args.config, args.method)
                if args.command == "smoke"
                else check(args.config, args.connect)
            )
        except (ValueError, OSError, RuntimeError) as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 1
    if not argv or argv[0] in ("-h", "--help"):
        print("Firmen-PC: main.py check [--connect], smoke, run, signatures, report, compare-excel")
        print("run/signatures nutzen dieselben Ergebnisformate wie die lokale Verarbeitung.")
        return 0
    if argv[0] not in ("run", "signatures", "report", "compare-excel", "prepare", "doctor"):
        print("Unbekannter API-Befehl; main.py --help verwenden", file=sys.stderr)
        return 1
    if argv[0] in ("run", "signatures", "prepare", "doctor") and not any(
        item == "--config" or item.startswith("--config=") for item in argv
    ):
        argv.extend(["--config", str(DEFAULT_CONFIG)])
    if argv[0] == "compare-excel" and not any(
        item == "--config" or item.startswith("--config=") for item in argv
    ):
        argv.extend(["--config", str(PROJECT_ROOT / "configs" / "excel.yaml")])
    from participant_bench.cli import main as analysis_main

    return analysis_main(argv)
