"""Explicit public checkpoint download, selecting one weight set and never Python model code."""

import copy
import json
import urllib.request
from pathlib import Path

from .io import file_hash, write_json
from .models import Unavailable, local_model_identity, range_download


def download(spec, transport="hub"):
    from huggingface_hub import HfApi, hf_hub_url, snapshot_download

    path = Path(spec.path)
    if (path / "download_manifest.json").exists():
        local_model_identity(spec, verify=True)
        print("Unlimited-OCR: vorhandene Gewichte verifiziert")
        return
    info = HfApi(token=False).model_info(spec.repo, revision=spec.revision, files_metadata=True)
    if info.sha != spec.revision:
        raise Unavailable("Modellrevision stimmt nicht mit der festgelegten Revision überein")
    index_url = hf_hub_url(spec.repo, "model.safetensors.index.json", revision=spec.revision)
    with urllib.request.urlopen(index_url, timeout=60) as response:
        index = json.load(response)
    weights = set(index["weight_map"].values())
    if not weights or any(Path(name).name != name or not name.endswith(".safetensors") for name in weights):
        raise Unavailable("Unerwarteter Safetensors-Index")
    allowed = {
        file.rfilename
        for file in info.siblings
        if file.rfilename in weights
        or (
            "/" not in file.rfilename
            and (
                file.rfilename.endswith((".json", ".jinja", ".txt", ".model")) or file.rfilename == "LICENSE"
            )
        )
    }
    if not weights <= allowed:
        raise Unavailable("Gewichtdateien im Modellindex fehlen")
    path.mkdir(parents=True, exist_ok=True)
    selected = copy.copy(info)
    selected.siblings = [file for file in info.siblings if file.rfilename in allowed]
    if transport == "range":
        range_download(spec, selected)
    else:
        snapshot_download(
            spec.repo,
            revision=spec.revision,
            local_dir=path,
            allow_patterns=sorted(allowed),
            token=False,
            max_workers=2,
        )
    hashes = {name: file_hash(path / name) for name in sorted(allowed)}
    write_json(
        path / "download_manifest.json",
        dict(
            repo=spec.repo,
            revision=spec.revision,
            license="MIT",
            sha256=hashes,
            implementation="native_transformers",
            trust_remote_code=False,
            weight_files=sorted(weights),
        ),
    )
    local_model_identity(spec, verify=True)
