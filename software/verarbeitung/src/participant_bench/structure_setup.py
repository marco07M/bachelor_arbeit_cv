"""Explicit provisioning of pinned public model assets; never invoked while analyzing documents."""

import json
from pathlib import Path

from .config import structure_settings
from .io import file_hash, write_json
from .progress import Progress
from .structure import model_manifest, runtime_paths


def download_snapshot(spec, destination):
    from huggingface_hub import constants, snapshot_download

    # --download is an explicit network action, even when the analysis terminal defaults to offline.
    previous = constants.HF_HUB_OFFLINE
    constants.HF_HUB_OFFLINE = False
    try:
        snapshot_download(repo_id=spec["repo"], revision=spec["revision"], local_dir=destination,
                          token=False, local_files_only=False,
                          allow_patterns=spec.get("patterns", ["*.json", "*.yml", "*.yaml", "*.pdiparams"]))
    finally:
        constants.HF_HUB_OFFLINE = previous


def setup_structures(config, methods=None, download=False):
    progress = Progress()
    selected = methods or list(dict.fromkeys("paddle_llm" if method == "ocr_vlm" else method
        for method in config.methods if method in config.structures or method == "ocr_vlm"))
    if not selected:
        raise ValueError("Keine Strukturverfahren konfiguriert")
    results = {}
    provisioned = set()
    for method in selected:
        settings = structure_settings(config, method)
        root = Path(settings.models_dir).resolve()
        if root in provisioned:
            continue
        provisioned.add(root)
        python, source, lock = runtime_paths(method, settings)
        if not python.is_file() or not lock.is_file():
            raise ValueError(f"Zuerst uv sync --locked --project {lock.parent.name} ausführen")
        if not download:
            results[method] = model_manifest(root, verify=True)
            continue
        sources = json.loads((source / ("paddle_sources.json" if method in ("paddle_structure", "paddle_llm", "ocr_vlm") else
                                        "docling_sources.json")).read_text(encoding="utf-8"))
        for name, spec in sources.items():
            progress.log(f"{method}: öffentliche Modellgewichte {name} laden; Revision {spec['revision']}")
            download_snapshot(spec, root / name)
        files = {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(root.rglob("*"))
                 if p.is_file() and ".cache" not in p.relative_to(root).parts
                 and p.name != "models-manifest.json"}
        manifest = dict(method=method, sources=sources, files=files, runtime_lock=file_hash(lock))
        write_json(root / "models-manifest.json", manifest)
        results[method] = manifest
        progress.log(f"{method}: {len(files)} Modelldateien lokal gespeichert und mit SHA-256 erfasst")
    return {name: {"model_files": len(manifest["files"]), "status": "verified"}
            for name, manifest in results.items()}
