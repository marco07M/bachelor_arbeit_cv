"""Explicit API entry for the shared roster benchmark; reference evaluation stays local."""

from pathlib import Path

from participant_bench.roster_benchmark.cli import main as benchmark_main

from .backend import enable

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "testframework/config.yaml"


def main(argv=None):
    enable()
    return benchmark_main(argv, default_config=DEFAULT_CONFIG, allow_api=True)
