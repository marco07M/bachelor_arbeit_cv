import argparse
import json
import sys
import uuid
from pathlib import Path

from .config import load_config
from .doctor import environment
from .io import write_json
from .models import download_models
from .ocr import OCR, generated_cache_files
from .pdf import prepare
from .runner import run
from .schema import GroundTruthPage, ModelResponse, PageResult
from .synthetic import generate


def main():
    parser = argparse.ArgumentParser(
        description="Lokaler Benchmark für Teilnehmerlisten (keine Cloud-Inferenz)"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "download-models", "prepare", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", type=Path, default=Path("configs/local.yaml"))
        if name == "doctor":
            sub.add_argument("--output", type=Path)
        if name == "download-models":
            sub.add_argument("--method", choices=["ocr_llm", "vlm"], action="append")
            sub.add_argument("--transport", choices=["hub", "range"], default="hub")
        if name in ("prepare", "run"):
            sub.add_argument("--input", type=Path, required=True)
        if name == "prepare":
            sub.add_argument("--output", type=Path)
        if name == "run":
            sub.add_argument("--offline", action="store_true", help="Inferenz ist immer lokal/offline")
            sub.add_argument("--manifest", type=Path)
            sub.add_argument("--ground-truth", type=Path)
            sub.add_argument("--scope", choices=["curated", "end-to-end"], default="end-to-end")
            sub.add_argument("--split", choices=["development", "test", "all"], default="all")
            sub.add_argument("--resume", type=Path)
    synthetic = commands.add_parser("synthetic")
    synthetic.add_argument("--output", type=Path, default=Path("data/synthetic"))
    commands.add_parser("schemas")
    clean = commands.add_parser("clean-cache")
    clean.add_argument("--config", type=Path, default=Path("configs/local.yaml"))
    clean.add_argument("--apply", action="store_true", help="Delete generated OCR JSON cache only")
    args = parser.parse_args()
    try:
        if args.command == "synthetic":
            print(generate(args.output))
        elif args.command == "schemas":
            root = Path("examples/schemas")
            for name, cls in (
                ("ground_truth", GroundTruthPage),
                ("model_response", ModelResponse),
                ("page_result", PageResult),
            ):
                write_json(root / f"{name}.schema.json", cls.model_json_schema())
            print(root)
        else:
            config = load_config(args.config)
            if args.command == "doctor":
                info = environment(config)
                print(json.dumps(info, ensure_ascii=False, indent=2))
                if args.output:
                    write_json(args.output, info)
            elif args.command == "download-models":
                download_models(config, args.method, args.transport)
            elif args.command == "prepare":
                output = args.output or Path("prepared") / uuid.uuid4().hex[:12]
                try:
                    ocr = OCR(config)
                except (OSError, RuntimeError) as exc:
                    print(f"OCR unavailable: {exc}; all nonblank pages retained for review", file=sys.stderr)
                    ocr = None
                prepare(args.input, config, output, ocr)
                print(output / "manifest.json")
            elif args.command == "run":
                _, summaries = run(
                    config, args.input, args.manifest, args.ground_truth, args.scope, args.split, args.resume
                )
                if any(s["status"] in ("failed", "unavailable") for s in summaries.values()):
                    return 2
            elif args.command == "clean-cache":
                root = (Path(config.cache_dir) / "ocr").resolve()
                workspace = Path.cwd().resolve()
                if (
                    not root.is_relative_to(workspace)
                    or Path(config.cache_dir).is_symlink()
                    or root.is_symlink()
                ):
                    raise ValueError("Cache cleanup restricted to real directories within project workspace")
                files = generated_cache_files(root)
                print(
                    f"{'Deleting' if args.apply else 'Dry run'}: {len(files)} generated OCR JSON files in {root}"
                )
                if args.apply:
                    for path in files:
                        path.unlink()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
