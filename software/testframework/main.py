"""Run using ../.venv/Scripts/python.exe; no separate model install and no API credentials."""

import os
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    from participant_bench.roster_benchmark.cli import main

    raise SystemExit(main())
