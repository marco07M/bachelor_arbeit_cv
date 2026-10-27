"""Company-PC entry point: OAuth token first, then model requests or PDF extraction."""

from participant_api.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
