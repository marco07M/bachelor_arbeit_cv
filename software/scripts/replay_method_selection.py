"""Reproduce the existing ONE-document development countercheck, never label it an independent pilot."""

import argparse
from pathlib import Path

from participant_bench.io import read_json, write_csv
from participant_bench.roster_benchmark.evaluation import identify_course
from participant_bench.selection import compare
from participant_bench.selection_config import load_policy
from participant_bench.selection_sample import freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--assist-comparison", type=Path)
    parser.add_argument("--stratum", choices=["printed", "mixed", "handwritten"], required=True)
    parser.add_argument("--quality-flags", required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/selection.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Neuen Ausgabeordner verwenden")
    identity = read_json(args.comparison / "identity.json")
    source = Path(identity["source_run"])
    manifest = read_json(source / "manifest.json")
    inputs = {p["sha256"]: p for p in manifest["inputs"] if p["kind"] == "pdf"}
    if len(inputs) != 1:
        parser.error("Dieser Helfer gilt nur für die bekannte einzelne Entwicklungs-PDF; sonst manuelles Inventar verwenden")
    args.output.mkdir(parents=True)
    rows = []
    for doc_id, item in inputs.items():
        course = identify_course(item["path"], set())
        rows.append(dict(document_id=doc_id, path=item["path"], class_id=course, dependency_group=course,
                         grouping_reviewed="true", prior_use="development", partition="development",
                         stratum=args.stratum, quality_flags=args.quality_flags))
    inventory = args.output / "inventory.csv"
    write_csv(inventory, rows)
    plan = freeze(inventory, args.policy, args.output / "plan.json")
    policy, _ = load_policy(args.policy)
    methods = read_json(args.comparison / "metrics.json")["methods"]
    reports = {key: args.comparison.resolve() for key, c in policy.candidates.items()
               if c.method in methods and key != "docling_vlm"}
    if args.assist_comparison:
        reports["docling_vlm"] = args.assist_comparison.resolve()
    output = compare(plan, args.output / "comparison", comparisons=reports, scope="development")
    print(output / "report.html")


if __name__ == "__main__":
    main()
