"""Evidence-based method selection; unknown evidence never becomes a numeric rating."""

from math import isfinite
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .config import ConfigModel, load_config


class Evidence(ConfigModel):
    value: float | None = Field(default=None, ge=0, le=1)
    reason: str
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported(self):
        if self.value is not None and not self.sources:
            raise ValueError("Numerische Bewertung benötigt einen überprüfbaren Beleg")
        return self


class Gate(ConfigModel):
    passed: bool | None = None
    reason: str
    sources: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported(self):
        if self.passed is not None and not self.sources:
            raise ValueError("Entschiedenes Ausschlusskriterium benötigt einen Beleg")
        return self


class Criterion(ConfigModel):
    weight: float = Field(gt=0, allow_inf_nan=False)
    definition: str
    rubric: str


class Candidate(ConfigModel):
    method: Literal["ocr_raw", "ocr_llm", "paddle_llm", "docling", "vlm", "ocr_vlm"]
    role: Literal["diagnostic", "structure", "ocr_llm", "vision", "hybrid"]
    profile: str
    description: str
    sources: list[str]
    gates: dict[str, Gate]
    ratings: dict[str, Evidence]


class SelectionPolicy(ConfigModel):
    version: Literal[1] = 1
    seed: int = 42
    target_lists: int = Field(default=40, ge=30, le=50)
    minimum_pilot_lists: int = Field(default=30, ge=30)
    minimum_pilot_groups: int = Field(default=5, ge=5)
    # Development / pilot / untouched final test; whole dependency groups only.
    split_ratios: tuple[float, float, float] = (.2, .6, .2)
    required_strata: list[str]
    gates: list[str]
    criteria: dict[str, Criterion]
    candidates: dict[str, Candidate]

    @model_validator(mode="after")
    def consistent(self):
        if any(not isfinite(x) or x <= 0 for x in self.split_ratios) or abs(sum(self.split_ratios) - 1) > 1e-8:
            raise ValueError("Drei positive Splitanteile mit Summe 1 erforderlich")
        if not self.criteria or not self.candidates or not self.required_strata:
            raise ValueError("Kriterien, Kandidaten und erforderliche Strata fehlen")
        for candidate in self.candidates.values():
            if set(candidate.gates) != set(self.gates) or set(candidate.ratings) != set(self.criteria):
                raise ValueError("Jeder Kandidat muss jedes Kriterium explizit bewerten, ggf. unbekannt")
        return self


def load_policy(path: Path):
    policy = SelectionPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    profiles = {}
    for key, candidate in policy.candidates.items():
        config = load_config(path.parent / candidate.profile)
        config.methods = [candidate.method]
        config.pdf.recursive = True
        config.pdf.include_images = False
        config.signature.backend = "opencv"
        from .config import Config
        from .models import require_offline

        config = Config.model_validate(config.model_dump())
        require_offline(config, True)
        if any(m.backend != "local" for m in config.models.values()):
            raise ValueError("Auswahlstudie erlaubt ausschließlich lokale Modelle")
        assist = bool(config.structures.get("docling") and config.structures["docling"].vlm_assist)
        if candidate.method == "docling" and assist != (candidate.role == "hybrid"):
            raise ValueError("Docling-Baseline und VLM-Assist müssen getrennte Kandidaten sein")
        profiles[key] = config.model_dump()
    return policy, profiles


def matrix(policy: SelectionPolicy):
    total = sum(c.weight for c in policy.criteria.values())
    rows, summaries = [], {}
    for key, candidate in policy.candidates.items():
        weight, credit = 0.0, 0.0
        for name, criterion in policy.criteria.items():
            evidence = candidate.ratings[name]
            if evidence.value is not None:
                weight += criterion.weight
                credit += criterion.weight * evidence.value
            rows.append(dict(candidate=key, criterion=name, weight=criterion.weight / total,
                             value=evidence.value, reason=evidence.reason, sources=" | ".join(evidence.sources)))
        failed = [name for name, gate in candidate.gates.items() if gate.passed is False]
        unknown = [name for name, gate in candidate.gates.items() if gate.passed is None]
        summaries[key] = dict(
            role=candidate.role,
            eligibility="diagnostic_only" if candidate.role == "diagnostic" else
                        "excluded" if failed else "open" if unknown else "eligible",
            failed_gates=failed, open_gates=unknown, evidence_coverage=weight / total,
            # Partial credit is an interval, not a mean over convenient known criteria.
            score_lower_bound=credit / total, score_upper_bound=(credit + total - weight) / total,
            weighted_score=credit / total if abs(weight - total) < 1e-8 else None,
        )
    return rows, summaries
