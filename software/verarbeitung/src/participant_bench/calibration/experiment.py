"""Controlled experiments: develop, fit thresholds, independent audit, then freeze for one test."""

import copy
import importlib.metadata
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError

from ..config import Config, ConfigModel, load_config
from ..io import digest, file_hash, read_json, write_csv, write_json, write_jsonl
from ..models import model_identity, require_offline
from ..ocr import OCR
from ..progress import Progress
from ..runner import run
from .confidence import evaluate_policy, tune
from .dataset import load_dataset, partitions
from .metrics import assess
from .report import export_report

VERSION = "ocr-calibration-v1"


def implementation_fingerprint() -> dict:
    root = Path(__file__).resolve().parents[1]
    sources = (
        "ocr.py",
        "image_preprocessing.py",
        "rules.py",
        "models.py",
        "schema.py",
        "evaluation.py",
        "calibration/confidence.py",
        "calibration/metrics.py",
        "calibration/experiment.py",
    )
    return dict(
        packages={
            name: importlib.metadata.version(name)
            for name in ("pymupdf", "pillow", "numpy", "opencv-python-headless", "scipy", "pytesseract")
        },
        sources={name: file_hash(root / name) for name in sources},
    )


def pipeline_fingerprint(config) -> dict:
    active = {method for method in config.methods if method != "ocr_rules"}
    if config.signature.backend in ("local_vlm", "vlm"):
        active.add("vlm")
    return dict(
        ocr=OCR(config).identity,
        models={name: model_identity(config.models[name]) for name in sorted(active)},
        **implementation_fingerprint(),
    )


class Variant(ConfigModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    method: Literal["ocr_rules", "ocr_llm"] | None = None
    overrides: dict = Field(default_factory=dict)


class ExperimentConfig(ConfigModel):
    base_config: str = "../configs/smoke.yaml"
    method: Literal["ocr_rules", "ocr_llm"] = "ocr_rules"
    variants: list[Variant] = Field(default_factory=list)
    calibrator: Literal["sigmoid", "isotonic"] = "sigmoid"
    target_precision: float = Field(default=0.98, gt=0, le=1)
    min_samples: int = Field(default=50, ge=10)
    min_class: int = Field(default=5, ge=2)
    min_documents: int = Field(default=3, ge=2)
    min_accepted: int = Field(default=10, ge=2)
    minimum_quality_gain: float = Field(default=0, ge=0)
    minimum_runtime_gain: float = Field(default=0.05, gt=0, lt=1)
    review_seconds_per_field: float = Field(default=10, ge=0)


def merge(base: dict, patch: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = (
            merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else copy.deepcopy(value)
        )
    return result


def load_experiment(path: Path):
    options = ExperimentConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    names = [v.name for v in options.variants]
    if "baseline" in names or len(set(names)) != len(names):
        raise ValueError("Varianten müssen eindeutig sein; baseline ist reserviert")
    baseline = load_config((path.parent / options.base_config).resolve())
    configurations = {}
    for variant in [Variant(name="baseline")] + options.variants:
        data = merge(baseline.model_dump(), variant.overrides)
        method = variant.method or options.method
        data["methods"] = [method]
        config = Config.model_validate(data)
        # Explicitly forbid all configured remote models, without reading any credential environment.
        if any(model.backend != "local" for model in config.models.values()):
            raise ValueError("Kalibrierung ist ausschließlich lokal; externe Backends nicht zugelassen")
        require_offline(config, True)
        configurations[variant.name] = config
    return options, configurations


def stage(config, truths, dataset, output, ledger, progress):
    if not truths:
        return None
    config = config.model_copy(deep=True)
    key = digest(
        dict(
            config=config.model_dump(),
            pages=[(p.document_id, p.page_number) for p in truths],
            dataset=dataset["dataset_id"],
            implementation=VERSION,
        )
    )
    state = read_json(ledger) if ledger.exists() else {}
    if key in state and state[key].get("run"):
        folder = output / state[key]["run"]
        if (folder / "run_timing.json").exists():
            progress.log("Bereits abgeschlossenen lokalen Lauf wiederverwenden")
            return folder
    if key not in state:
        state[key] = {"slot": len(state), "run": None}
        write_json(ledger, state)
    index = state[key]["slot"]
    inputs = output / "i" / str(index)
    inputs.mkdir(parents=True, exist_ok=True)
    for document_id in sorted({p.document_id for p in truths}):
        source = dataset["inventory"][document_id]["source"]
        target = inputs / (document_id + ".pdf")
        if target.exists() and file_hash(target) != document_id:
            raise ValueError("Experiment-Eingabekopie verändert")
        if not target.exists():
            shutil.copy2(source, target)
        if file_hash(target) != document_id:
            raise ValueError("Original während der Experimentvorbereitung verändert")
    truth_path = output / "i" / f"{index}.jsonl"
    write_jsonl(truth_path, [p.model_dump() for p in truths])
    config.output_dir = str(output / "r" / str(index))
    previous = output / state[key]["run"] if state[key]["run"] else None
    if previous is None:
        candidates = list(Path(config.output_dir).glob("*/identity.json"))
        previous = candidates[0].parent if len(candidates) == 1 else None
    folder, _ = run(config, inputs, truth_path=truth_path, offline=True, resume=previous)
    state[key]["run"] = str(folder.relative_to(output))
    write_json(ledger, state)
    return folder


def score_stage(folder, config, truths, dataset) -> dict:
    if folder is None:
        return dict(
            structured=None, events=[], errors=[], error_counts={}, text={}, page_timings=[], text_pages=[]
        )
    result = assess(folder, config.methods[0], truths, dataset["texts"], dataset["quality_flags"])
    summary = read_json(folder / "summary.json")[config.methods[0]]
    result["runtime"] = summary
    result["run"] = str(folder)
    write_json(
        folder / "calibration_metrics.json",
        {k: v for k, v in result.items() if k not in ("events", "errors")},
    )
    write_csv(folder / "field_confidences.csv", result["events"])
    write_csv(folder / "error_categories.csv", result["errors"])
    write_csv(folder / "normalized_fields.csv", result["normalized_fields"])
    return result


def ranking(result: dict) -> tuple:
    if not result.get("structured"):
        return (-1, -1, float("-inf"))
    metrics = result["structured"]
    return (
        metrics["field_prf"]["f1"]["value"] or 0,
        metrics["assignment"]["complete_row_coverage"]["value"] or 0,
        -result.get("runtime", {}).get("full_pipeline_charged_seconds", float("inf")),
    )


def better_on_audit(candidate: dict, baseline: dict, options) -> tuple[bool, str]:
    if not candidate.get("structured") or not baseline.get("structured"):
        return False, "insufficient_validation_groups"
    cm, bm = candidate["structured"], baseline["structured"]
    if cm["field_prf"]["f1"]["value"] is None or bm["field_prf"]["f1"]["value"] is None:
        return False, "insufficient_reference_fields"
    if cm["counts"]["technical_failure_pages"] > bm["counts"]["technical_failure_pages"]:
        return False, "technical_failure_regression"
    cs, bs = cm["signature"]["prf"]["recall"]["value"], bm["signature"]["prf"]["recall"]["value"]
    if cs is not None and bs is not None and cs < bs:
        return False, "signature_recall_regression"
    if any(
        cm["fields"][f]["prf"]["recall"]["value"] is not None
        and bm["fields"][f]["prf"]["recall"]["value"] is not None
        and cm["fields"][f]["prf"]["recall"]["value"] < bm["fields"][f]["prf"]["recall"]["value"]
        for f in cm["fields"]
    ):
        return False, "field_recall_regression"
    cr, br = ranking(candidate), ranking(baseline)
    if cr[0] > br[0] + options.minimum_quality_gain and cr[1] >= br[1]:
        return True, "independent_validation_quality_gain"
    if cr[:2] == br[:2] and -br[2] > 0 and -cr[2] <= -br[2] * (1 - options.minimum_runtime_gain):
        return True, "equal_quality_lower_runtime"
    return False, "no_independent_improvement"


def experiment(dataset_folder: Path, config_path: Path, output: Path | None = None, resume=False) -> Path:
    if resume and output is None:
        raise ValueError("Für --resume den bestehenden Experimentordner mit --output angeben")
    options, configurations = load_experiment(config_path)
    try:
        dataset = load_dataset(dataset_folder)
    except ValidationError:
        raise ValueError(
            "Referenzformat ungültig; Feldstatus, Seiten, Signaturen und Boxen in CSV prüfen"
        ) from None
    parts = partitions(dataset)
    output = output or Path("runs") / ("c-" + uuid.uuid4().hex[:8])
    identity = dict(
        version=VERSION,
        dataset_id=dataset["dataset_id"],
        options=options.model_dump(),
        implementation=implementation_fingerprint(),
        configurations={name: config.model_dump() for name, config in configurations.items()},
    )
    if output.exists():
        if not resume or read_json(output / "experiment.json") != identity:
            raise ValueError(
                "Experiment existiert oder Identität verändert; nur passenden Lauf mit --resume fortsetzen"
            )
        if (output / "frozen.json").exists():
            return output
    else:
        output.mkdir(parents=True)
        write_json(output / "experiment.json", identity)
    progress = Progress(output / "progress.log")
    progress.log("OCR-Kalibrierung: Entwicklung; Testdaten bleiben unberührt")
    development = {}
    ledger = output / "ledger.json"
    for name, config in configurations.items():
        progress.log(f"Entwicklungsvariante {name}; {len(parts['development'])} Seiten")
        folder = stage(config, parts["development"], dataset, output, ledger, progress)
        development[name] = score_stage(folder, config, parts["development"], dataset)
    candidate = max(development, key=lambda name: ranking(development[name]))
    validation, policies, audits = {}, {}, {}
    for name in dict.fromkeys(("baseline", candidate)):
        config = configurations[name]
        progress.log(f"Validierung {name}: Schwellenwerte und unabhängige Kontrollgruppe")
        fit_folder = stage(config, parts["validation_fit"], dataset, output, ledger, progress)
        fit_result = score_stage(fit_folder, config, parts["validation_fit"], dataset)
        policy = tune(development[name]["events"], fit_result["events"], options)
        audit_folder = stage(config, parts["validation_audit"], dataset, output, ledger, progress)
        audit_result = score_stage(audit_folder, config, parts["validation_audit"], dataset)
        audits[name] = evaluate_policy(
            audit_result["events"],
            policy,
            audit=True,
            min_accepted=options.min_accepted,
            min_documents=options.min_documents,
        )
        validation[name], policies[name] = audit_result, policy
    approved, reason = (
        better_on_audit(validation[candidate], validation["baseline"], options)
        if candidate != "baseline"
        else (False, "baseline_best_on_development")
    )
    if len({p.dependency_group for p in parts["validation_audit"]}) < options.min_documents:
        approved, reason = False, "insufficient_independent_validation_groups"
    selected = candidate if approved else "baseline"
    if implementation_fingerprint() != identity["implementation"] or any(
        file_hash(dataset["folder"] / name) != expected for name, expected in dataset["hashes"].items()
    ):
        raise ValueError("Implementierung oder Referenzen während des Experiments verändert")
    frozen = dict(
        version=VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        dataset_id=dataset["dataset_id"],
        dataset_folder=str(dataset_folder.resolve()),
        selected=selected,
        proposed=candidate,
        approval_reason=reason,
        config=configurations[selected].model_dump(),
        policy=policies[selected],
        options=options.model_dump(),
        pipeline=pipeline_fingerprint(configurations[selected]),
        partition_documents={
            name: sorted({p.document_id for p in parts[name]})
            for name in ("development", "validation_fit", "validation_audit", "test")
        },
        selection_run=validation[selected].get("run"),
        test_used=False,
    )
    frozen["seal"] = digest(frozen)
    write_json(output / "frozen.json", frozen)
    bundle = dict(
        identity=identity,
        selected=selected,
        proposed=candidate,
        approval_reason=reason,
        development=development,
        validation=validation,
        policies=policies,
        audit=audits,
    )
    write_json(output / "comparison.json", bundle)
    export_report(output, bundle, options.review_seconds_per_field)
    progress.log(f"Eingefroren: {selected}; {reason}; Testlauf separat starten")
    return output


def final_test(output: Path, resume=False) -> Path:
    frozen = read_json(output / "frozen.json")
    seal = frozen.pop("seal")
    if digest(frozen) != seal or frozen["version"] != VERSION:
        raise ValueError("Eingefrorene Konfiguration oder Schwellenwerte verändert")
    dataset = load_dataset(Path(frozen["dataset_folder"]))
    if dataset["dataset_id"] != frozen["dataset_id"]:
        raise ValueError("Referenzdatensatz nach Kalibrierung verändert")
    config = Config.model_validate(frozen["config"])
    if any(model.backend != "local" for model in config.models.values()):
        raise ValueError("Finale OCR-Evaluation ist ausschließlich lokal")
    if pipeline_fingerprint(config) != frozen["pipeline"]:
        raise ValueError(
            "OCR-Engine, lokale Modelle, Pakete oder Implementierung nach Kalibrierung verändert"
        )
    target = output / "test"
    if target.exists():
        if (
            not resume
            or (target / "final_metrics.json").exists()
            or read_json(target / "started.json")["seal"] != seal
        ):
            raise FileExistsError(
                "Finaler Test wurde bereits gestartet/abgeschlossen; nur unveränderten Abbruch mit --resume fortsetzen"
            )
    else:
        target.mkdir()
        write_json(
            target / "started.json", {"seal": seal, "created_at": datetime.now(timezone.utc).isoformat()}
        )
    progress = Progress(target / "progress.log")
    truths = partitions(dataset)["test"]
    folder = stage(config, truths, dataset, target, target / "ledger.json", progress)
    result = score_stage(folder, config, truths, dataset)
    policy_result = evaluate_policy(result["events"], frozen["policy"])
    bundle = dict(
        selected=frozen["selected"],
        proposed=frozen["selected"],
        approval_reason="final_test_frozen_without_refit",
        development={},
        test={frozen["selected"]: result},
        policies={frozen["selected"]: frozen["policy"]},
        audit={frozen["selected"]: policy_result},
        seal=seal,
        dataset_id=dataset["dataset_id"],
    )
    write_json(target / "final_metrics.json", bundle)
    export_report(target, bundle, frozen["options"]["review_seconds_per_field"])
    return target
