from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from ..config import ConfigModel
from ..excel_reference import ExcelConfig


class MatchingConfig(ConfigModel):
    # Missing mode in historical snapshots must preserve their conservative scoring.
    mode: Literal["conservative", "best_fit"] = "conservative"
    minimum_similarity: float = Field(default=0.80, ge=0, le=1)
    minimum_name_similarity: float = Field(default=0.70, ge=0, le=1)
    ambiguity_margin: float = Field(default=0.02, ge=0, le=0.5)
    case_sensitive: bool = False
    score_uncertain_values: bool = True
    # Absent in historical report snapshots: preserve their original calculation.
    ignore_leading_user_id_zeros: bool = False


class ReferenceConfig(ExcelConfig):
    encoding: str = "utf-8-sig"
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)
    merge_identical_duplicates: bool = False


class BenchmarkConfig(ConfigModel):
    input_dir: str = "eingabe_pdfs"
    reference_dir: str = "referenz"
    reference_file: str | None = None
    extraction_config: str = "../configs/benchmark-unlimited.yaml"
    output_dir: str = "ergebnisse"
    signature_detail_checks: bool = False
    reference: ReferenceConfig = Field(default_factory=ReferenceConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)


def load_config(path: Path):
    return BenchmarkConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def resolve(base: Path, value: str | Path):
    return (base / value).resolve()


def reference_path(config: BenchmarkConfig, base: Path, override: Path | None = None):
    if override or config.reference_file:
        path = override.resolve() if override else resolve(base, config.reference_file)
        if not path.is_file():
            raise ValueError("Die angegebene Referenzdatei fehlt")
        return path
    folder = resolve(base, config.reference_dir)
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".csv", ".xlsx")
                   and not p.name.startswith("~$")) if folder.is_dir() else []
    if len(files) != 1:
        raise ValueError("Genau eine CSV- oder XLSX-Datei in testframework/referenz ablegen oder --reference angeben")
    return files[0]
