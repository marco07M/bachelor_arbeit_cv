"""Independent CLI for course-scoped fuzzy roster benchmarks."""

import argparse
import json
import sys
from pathlib import Path

from ..config import ALL_METHODS
from .config import load_config, reference_path, resolve
from .evaluation import evaluate_run
from .runner import preflight, run_benchmark

DEFAULT_CONFIG = Path(__file__).resolve().parents[4] / "testframework/config.yaml"


def main(argv=None, *, default_config=DEFAULT_CONFIG, allow_api=False):
    description = "API-Testframework" if allow_api else "Lokales Testframework"
    parser = argparse.ArgumentParser(description=description + ": PDFs gegen Excel/CSV vergleichen")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("analyze", "metadata-template"):
        analysis=commands.add_parser(name,help="Wissenschaftliche Analyse in neuem Bericht / manuelle Metadatenvorlage")
        analysis.add_argument("--report",type=Path,required=True)
        analysis.add_argument("--output",type=Path,required=True)
        analysis.add_argument("--source-run",type=Path)
        if name=="analyze":
            analysis.add_argument("--metadata",type=Path)
            analysis.add_argument("--phase",choices=["all","development","pilot","test"],default="all")
            analysis.add_argument("--resamples",type=int,default=2000)
            analysis.add_argument("--seed",type=int,default=42)
            analysis.add_argument("--minimum-groups",type=int,default=10)
            analysis.add_argument("--additional-report",action="append",help="KANDIDAT=Vergleichsordner, z.B. docling_vlm=...")
    for name in ("details", "assignments"):
        detail = commands.add_parser(name, help="Gespeicherten Vergleich erklären; details: Feldberechnung, assignments: Namenszuordnung")
        detail.add_argument("--report", type=Path, required=True, help="Ordner mit gespeichertem Testframework-Vergleich")
        detail.add_argument("--source-run", type=Path, help="Verschobener Quelllauf; Prüfsummen müssen übereinstimmen")
    for name in ("check", "run", "compare"):
        sub = commands.add_parser(name)
        sub.add_argument("--config", type=Path, default=default_config)
        sub.add_argument("--reference", type=Path, help="CSV oder XLSX; sonst genau eine Datei im Referenzordner")
        if name != "compare":
            sub.add_argument("--input", type=Path, help="PDF-Eingabeordner einschließlich Unterordnern")
        if name != "check":
            sub.add_argument("--method", choices=list(ALL_METHODS), action="append")
            sub.add_argument("--matching-mode", choices=["conservative", "best_fit"], help="Zuordnungsmodus für diesen Vergleich")
        if name == "run":
            sub.add_argument("--resume", type=Path, help="Abgebrochenen unveränderten Extraktionslauf fortsetzen")
            sub.add_argument("--extraction-config", type=Path, help="Anderes Profil für die Modellverarbeitung")
            sub.add_argument("--manifest", type=Path, help="Vorhandenes geprüftes Seitenmanifest mit manuellen Rotationen")
        if name == "compare":
            sub.add_argument("--run", type=Path, required=True, help="Vorhandener Extraktionslauf; keine neue Inferenz")
            sub.add_argument("--output", type=Path, help="Neuer, noch nicht vorhandener Ausgabeordner")
    args = parser.parse_args(argv)
    try:
        if args.command in ("analyze","metadata-template"):
            from ..selection import bindings
            from .scientific import metadata_template, reanalyze

            if args.command=="metadata-template":
                print(metadata_template(args.report,args.output,args.source_run))
            else:
                result=reanalyze(args.report,args.output,metadata=args.metadata,phase=args.phase,
                    source_run=args.source_run,resamples=args.resamples,seed=args.seed,minimum_groups=args.minimum_groups,
                    additional_reports=bindings(args.additional_report))
                print(f"Wissenschaftlicher Bericht: {(args.output/'report.html').resolve()}")
                print(f"{result['courses']} Schulungen, {result['groups']} Gruppen; keine neue Inferenz.")
            return 0
        if args.command in ("details", "assignments"):
            from .assignment_report import render_assignments
            from .detail_report import render_details

            renderer = render_assignments if args.command == "assignments" else render_details
            print(renderer(args.report, source_run=args.source_run))
            return 0
        config = load_config(args.config)
        if args.command != "check" and args.matching_mode:
            config.matching.mode = args.matching_mode
        if args.command == "run" and args.extraction_config:
            config.extraction_config = str(args.extraction_config.resolve())
        base = args.config.resolve().parent
        if args.command == "check":
            *_, overview = preflight(config, base, args.input, args.reference)
            print(json.dumps(dict(overview, model_inference=False, network_contacted=False), ensure_ascii=True, indent=2))
            return 0
        if args.command == "run":
            options = dict(input_override=args.input, reference_override=args.reference,
                           methods=args.method, resume=args.resume)
            if args.manifest is not None:
                options["manifest_path"] = args.manifest
            if allow_api:
                options["allow_api"] = True
            output, metrics = run_benchmark(config, base, **options)
        else:
            reference = reference_path(config, base, args.reference)
            output, metrics = evaluate_run(args.run, reference, config, resolve(base, config.output_dir),
                                           args.method, output=args.output)
        for method, score in metrics.items():
            value = score.get("score_percent")
            if value is None:
                print(f"{method}: kein Teilnehmerfeldscore ({score.get('reason', 'keine bewertbaren Referenzfelder')})")
            else:
                overall = score["overall"]
                print(f"{method}: Levenshtein-Feld-F1 {value:.2f}%; "
                      f"{overall['exact_fields']}/{overall['reference_fields']} Referenzfelder exakt; "
                      f"{score['missing_participants']} Personen fehlen, {score['extra_participants']} zusätzlich")
        print(f"Vergleichsbericht: {(output / 'report.html').resolve()}")
        return 0
    except Exception as exc:
        # No reference names/IDs or model prompts are printed; audit values stay in local result files.
        if isinstance(exc, (ValueError, OSError)):
            print(f"Testframework: {exc}", file=sys.stderr)
        else:
            print(f"Testframework fehlgeschlagen ({type(exc).__name__}); Dateien und Konfiguration prüfen", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
