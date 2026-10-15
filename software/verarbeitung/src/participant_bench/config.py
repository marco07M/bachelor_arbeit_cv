from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PDFConfig(ConfigModel):
    dpi: int = Field(default=220, ge=100, le=600)
    recursive: bool = False
    auto_orient: bool = True
    osd_min_confidence: float = 5


class OCRConfig(ConfigModel):
    command: str = "auto"
    languages: str = "deu+eng"
    psm: int = Field(default=6, ge=3, le=13)
    timeout_seconds: int = Field(default=120, ge=1)
    remove_grid_lines: bool = True


class RulesConfig(ConfigModel):
    header_aliases: dict[str, list[str]] = Field(default_factory=dict)
    columns: dict[str, tuple[float, float]] = Field(default_factory=dict)
    body_top: float | None = Field(default=None, ge=0, le=1)
    body_bottom: float = Field(default=0.96, gt=0, le=1)
    row_tolerance: float = Field(default=0.008, gt=0, le=0.1)

    @model_validator(mode="after")
    def valid_columns(self):
        for name, (left, right) in self.columns.items():
            if name not in {
                "row_ref",
                "first_name",
                "last_name",
                "personnel_number",
                "department",
                "signature",
            }:
                raise ValueError(f"Unknown column {name}")
            if not 0 <= left < right <= 1:
                raise ValueError("Column intervals must be normalized and ordered")
        return self


class SignatureConfig(ConfigModel):
    blank_ink_fraction: float = Field(default=0.0005, ge=0, le=0.1)
    component_min_area: int = Field(default=8, ge=1)


class ModelConfig(ConfigModel):
    repo: str
    revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    path: str
    dtype: Literal["bfloat16", "float16", "float32"] = "bfloat16"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    gpu_memory_gib: int = Field(default=10, ge=1)
    cpu_memory_gib: int = Field(default=32, ge=1)
    max_input_tokens: int = Field(default=12000, ge=128, le=32768)
    max_new_tokens: int = Field(default=2048, ge=1)
    do_sample: bool = False
    temperature: float = Field(default=0.7, gt=0)
    min_pixels: int = Field(default=65536, ge=1024)
    max_pixels: int = Field(default=1048576, ge=1024)
    tile_height: int | None = Field(default=None, ge=128)
    tile_overlap: int = Field(default=0, ge=0)
    warmup: bool = True

    @model_validator(mode="after")
    def valid_tiles(self):
        if self.tile_height and self.tile_overlap >= self.tile_height:
            raise ValueError("tile_overlap must be smaller than tile_height")
        if self.max_pixels < self.min_pixels:
            raise ValueError("max_pixels must be >= min_pixels")
        return self


class CostsConfig(ConfigModel):
    kind: Literal["scenario", "measured"] = "scenario"
    volume: int | None = Field(default=None, ge=0)
    hourly_rate_eur: float | None = Field(default=None, ge=0)
    manual_minutes_per_page: float | None = Field(default=None, ge=0)
    review_minutes_per_page: float | None = Field(default=None, ge=0)
    local_operating_eur_per_page: float | None = Field(default=None, ge=0)
    development_hours: float | None = Field(default=None, ge=0)
    energy_kwh_per_page: float | None = Field(default=None, ge=0)
    energy_basis: Literal["measured", "assumed"] | None = None
    electricity_eur_per_kwh: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def energy_label(self):
        if self.energy_kwh_per_page is not None and self.energy_basis is None:
            raise ValueError("Energy requires measured/assumed basis")
        return self


class Config(ConfigModel):
    methods: list[Literal["ocr_rules", "ocr_llm", "vlm"]]
    seed: int = 42
    output_dir: str = "runs"
    cache_dir: str = ".cache/participant-bench"
    cache_max_gb: float = Field(default=2, ge=0)
    pdf: PDFConfig = Field(default_factory=PDFConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    signature: SignatureConfig = Field(default_factory=SignatureConfig)
    models: dict[str, ModelConfig] = Field(default_factory=dict)
    costs: CostsConfig = Field(default_factory=CostsConfig)

    @model_validator(mode="after")
    def unique_methods(self):
        if not self.methods or len(set(self.methods)) != len(self.methods):
            raise ValueError("Methods must be nonempty and unique")
        return self


def load_config(path: Path) -> Config:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "extends" in data:
        base = load_config(path.parent / data.pop("extends")).model_dump()
        base.update(data)
        data = base
    return Config.model_validate(data)
