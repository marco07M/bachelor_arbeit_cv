"""Use the company-PC environment and API models for the shared Excel/CSV benchmark."""

import os
from pathlib import Path

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    from participant_api.benchmark import main

    raise SystemExit(main())
