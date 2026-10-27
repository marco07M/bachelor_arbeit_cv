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
from .progress import Progress
from .report import refresh_report
from .runner import run
from .schema import (
    GroundTruthPage,
    ModelResponse,
    OCRPageResponse,
    PageResult,
    SignatureLocations,
    SignatureResponse,
    VisualPageResponse,
)
from .synthetic import generate


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Teilnehmerlisten auslesen: lokale Modelle und lokale OCR"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "download-models", "prepare", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", type=Path, default=Path("configs/local.yaml"))
        if name == "doctor":
            sub.add_argument("--output", type=Path)
        if name == "download-models":
            sub.add_argument("--method", choices=["ocr_llm", "vlm", "unlimited_ocr"], action="append")
            sub.add_argument("--transport", choices=["hub", "range"], default="hub")
        if name in ("prepare", "run"):
            sub.add_argument("--input", type=Path, required=True)
        if name == "prepare":
            sub.add_argument("--output", type=Path)
        if name == "run":
            sub.add_argument("--offline", action="store_true", help="Nur lokale Modelle erlauben")
            sub.add_argument("--manifest", type=Path)
            sub.add_argument("--ground-truth", type=Path)
            sub.add_argument("--scope", choices=["curated", "end-to-end"], default="end-to-end")
            sub.add_argument("--split", choices=["development", "validation", "test", "all"], default="all")
            sub.add_argument("--resume", type=Path)
    synthetic = commands.add_parser("synthetic")
    synthetic.add_argument("--output", type=Path, default=Path("data/synthetic"))
    commands.add_parser("schemas")
    refresh = commands.add_parser("report", help="Bericht und OCR-Klartext aus gespeicherten Ergebnissen aktualisieren")
    refresh.add_argument("--run", type=Path, required=True)
    assign = commands.add_parser("assign-unlimited", help="Gespeicherten Unlimited-OCR-Text lokal mit LLM zuordnen")
    assign.add_argument("--run", type=Path, required=True)
    assign.add_argument("--config", type=Path, default=Path("configs/unlimited-ocr-llm.yaml"))
    assign.add_argument("--output", type=Path)
    assign.add_argument("--offline", action="store_true", help="Zuordnung verwendet immer ein lokales LLM")
    signatures = commands.add_parser("signatures", help="Nur Unterschriften vorhandener Ergebnisse nachprüfen")
    signatures.add_argument("--run", type=Path, required=True)
    signatures.add_argument("--config", type=Path, default=Path("configs/local.yaml"))
    signatures.add_argument("--method", choices=["ocr_rules", "ocr_llm", "vlm", "unlimited_ocr"], action="append")
    signatures.add_argument("--output", type=Path)
    signatures.add_argument("--offline", action="store_true", help="Nur lokale Modelle erlauben")
    clean = commands.add_parser("clean-cache")
    clean.add_argument("--config", type=Path, default=Path("configs/local.yaml"))
    clean.add_argument("--apply", action="store_true", help="Delete generated OCR JSON cache only")
    excel = commands.add_parser("compare-excel", help="Extraktion nachträglich mit einer lokalen Excel-Kursliste vergleichen")
    excel.add_argument("--run", type=Path, required=True)
    excel.add_argument("--excel", type=Path, required=True)
    excel.add_argument("--config", type=Path, default=Path("configs/excel.yaml"))
    excel.add_argument("--sheet", help="Excel-Blatt; überschreibt die Konfiguration")
    excel.add_argument("--course-map", type=Path, help="Optionale CSV mit document_id,class_id")
    excel.add_argument("--method", choices=["ocr_rules", "ocr_llm", "vlm", "unlimited_ocr"], action="append")
    excel.add_argument("--output", type=Path)
    reference = commands.add_parser("ocr-reference", help="Manuelle CSV-Referenzstruktur ohne Modellvorschläge anlegen")
    reference.add_argument("--input", type=Path, required=True)
    reference.add_argument("--output", type=Path, required=True)
    reference.add_argument("--sample-documents", type=int)
    reference.add_argument("--seed", type=int, default=42)
    split = commands.add_parser("ocr-split", help="Geprüfte Dokumentgruppen in Entwicklung/Validierung/Test einfrieren")
    split.add_argument("--dataset", type=Path, required=True)
    split.add_argument("--seed", type=int, default=42)
    calibrate = commands.add_parser("ocr-calibrate", help="Lokale OCR-Varianten und Feldkonfidenzen anhand Referenzen prüfen")
    calibrate.add_argument("--dataset", type=Path, required=True)
    calibrate.add_argument("--config", type=Path, default=Path("configs/calibration.yaml"))
    calibrate.add_argument("--output", type=Path)
    calibrate.add_argument("--resume", action="store_true")
    final = commands.add_parser("ocr-final", help="Eingefrorene Auswahl einmal auf unabhängigem Testset evaluieren")
    final.add_argument("--experiment", type=Path, required=True)
    final.add_argument("--resume", action="store_true", help="Nur abgebrochenen unveränderten finalen Lauf fortsetzen")
    apply_ocr = commands.add_parser("ocr-apply", help="Eingefrorene lokale OCR und Prüfregeln ohne Referenzlabels anwenden")
    apply_ocr.add_argument("--experiment", type=Path, required=True)
    apply_ocr.add_argument("--input", type=Path, required=True)
    apply_ocr.add_argument("--output", type=Path)
    text_eval = commands.add_parser("evaluate-ocr", help="OCR-Text nachträglich mit geprüften Seitentranskripten vergleichen")
    text_eval.add_argument("--run", type=Path, required=True)
    text_eval.add_argument("--references", type=Path, required=True)
    text_eval.add_argument("--method", default="unlimited_ocr")
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate-ocr":
            from .ocr_evaluation import evaluate_text

            print(evaluate_text(args.run, args.references, args.method))
        elif args.command == "ocr-reference":
            from .calibration.dataset import initialize

            print(initialize(args.input, args.output, args.sample_documents, args.seed))
        elif args.command == "ocr-split":
            from .calibration.dataset import split_dataset

            print(split_dataset(args.dataset, args.seed))
        elif args.command == "ocr-calibrate":
            from .calibration.experiment import experiment

            print(experiment(args.dataset, args.config, args.output, args.resume) / "report.html")
        elif args.command == "ocr-final":
            from .calibration.experiment import final_test

            print(final_test(args.experiment, args.resume) / "report.html")
        elif args.command == "ocr-apply":
            from .calibration.apply import apply_frozen

            print(apply_frozen(args.experiment, args.input, args.output) / "report.html")
        elif args.command == "compare-excel":
            from .excel_comparison import compare_run
            from .excel_reference import load_excel_config

            config = load_excel_config(args.config)
            if args.sheet:
                config.sheet = args.sheet
            compare_run(args.run, args.excel, config, output=args.output,
                        mapping_file=args.course_map, methods=args.method)
        elif args.command == "assign-unlimited":
            from .unlimited_reassign import reassign_run

            print(reassign_run(args.run, load_config(args.config), args.output).resolve())
        elif args.command == "signatures":
            from .signature_review import recheck_run

            print(recheck_run(args.run, load_config(args.config), args.method, args.output, offline=args.offline).resolve())
        elif args.command == "report":
            print(refresh_report(args.run).resolve())
        elif args.command == "synthetic":
            print(generate(args.output))
        elif args.command == "schemas":
            root = Path("examples/schemas")
            for name, cls in (
                ("ground_truth", GroundTruthPage),
                ("model_response", ModelResponse),
                ("ocr_response", OCRPageResponse),
                ("vlm_response", VisualPageResponse),
                ("signature_response", SignatureResponse),
                ("signature_locations", SignatureLocations),
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
                progress = Progress()
                ocr = None
                try:
                    if config.pdf.auto_orient:
                        with progress.activity("Lokale OCR für die Seitenausrichtung initialisieren"):
                            ocr = OCR(config)
                except (OSError, RuntimeError) as exc:
                    print(f"OCR unavailable: {exc}; Seitenausrichtung manuell prüfen", file=sys.stderr)
                progress.log_path = output / "progress.log"
                prepare(args.input, config, output, ocr, progress=progress)
                print(output / "manifest.json")
            elif args.command == "run":
                _, summaries = run(
                    config, args.input, args.manifest, args.ground_truth, args.scope, args.split, args.resume,
                    offline=args.offline,
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
