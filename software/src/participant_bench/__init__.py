"""Local participant extraction benchmark; no document data is sent to a service."""

import os

for _key in ("HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
    os.environ[_key] = "1"
os.environ["WANDB_DISABLED"] = "true"
