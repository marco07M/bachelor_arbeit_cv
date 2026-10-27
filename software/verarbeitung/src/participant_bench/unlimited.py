"""Local Unlimited-OCR adapter using one persistent, version-isolated worker per method run."""

import base64
import importlib.metadata
import io
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field

from .config import ConfigModel
from .io import file_hash
from .models import Unavailable, local_model_identity
from .progress import Progress
from .unlimited_tables import clean_text, extract_tables, plain_text


class UnlimitedOptions(ConfigModel):
    runtime_python: str | None = None
    extraction: Literal["none", "table", "llm"] = "none"
    assignment_max_new_tokens: int = Field(default=4096, ge=128, le=16384)
    precision: Literal["auto", "bfloat16", "float16"] = "auto"
    attention: Literal["sdpa", "eager"] = "sdpa"
    crop_to_patches: bool = True
    prompt: str = "document parsing."
    no_repeat_ngram_size: int = Field(default=35, ge=0)
    no_repeat_ngram_window_size: int = Field(default=128, ge=1)
    min_free_gib: float = Field(default=9, ge=1)
    timeout_seconds: float = Field(default=600, gt=0)


def runtime_paths(options):
    root = Path(__file__).resolve().parents[3] / "unlimited_ocr_runtime"
    python = (
        Path(options.runtime_python)
        if options.runtime_python
        else root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    return python.resolve(), root / "worker.py", root / "uv.lock"


class UnlimitedModel:
    def __init__(self, method, config, progress=None):
        self.spec = config.models[method]
        self.options = UnlimitedOptions.model_validate(self.spec.options)
        self.progress = progress or Progress(enabled=False)
        if self.spec.device == "cpu":
            raise Unavailable("Unlimited-OCR verwendet CUDA; CPU-Inferenz ist nicht aktiviert")
        self.identity = local_model_identity(self.spec, verify=True, progress=self.progress)
        python, worker, lock = runtime_paths(self.options)
        if not python.is_file() or not lock.is_file():
            raise Unavailable(
                "Unlimited-OCR-Laufzeit fehlt: uv sync --locked --project unlimited_ocr_runtime"
            )
        self.progress.log(
            "Unlimited-OCR: isolierte native Laufzeit starten; keine API, kein Checkpoint-Python-Code"
        )
        self.log_path = Path(config.cache_dir) / "unlimited" / (uuid.uuid4().hex + ".log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [str(python), "-u", str(worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            encoding="utf-8",
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._responses = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        try:
            with self.progress.activity("Unlimited-OCR: native Modellgewichte laden und Warm-up ausführen"):
                self._resources = self.request(
                    dict(
                        command="init",
                        model_path=str(Path(self.spec.path).resolve()),
                        seed=config.seed,
                        options=self.options.model_dump(),
                        max_new_tokens=self.spec.max_new_tokens,
                        warmup=self.spec.warmup,
                    )
                )
        except Exception:
            self.close()
            raise
        self.calls = 0
        hardware = self._resources["hardware"]
        self.progress.log(f"Unlimited-OCR bereit: {hardware['gpu']}; Präzision {hardware['precision']}")

    def _read(self):
        try:
            for line in self.process.stdout:
                self._responses.put(line)
        finally:
            self._responses.put(None)

    def request(self, request):
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            line = self._responses.get(timeout=self.options.timeout_seconds)
        except (BrokenPipeError, OSError, queue.Empty):
            self.process.kill()
            raise Unavailable("Unlimited-OCR-Worker nicht erreichbar oder Zeitlimit überschritten") from None
        if line is None:
            raise Unavailable("Unlimited-OCR-Worker wurde beendet; lokale Laufzeitinstallation prüfen")
        try:
            response = json.loads(line)
        except ValueError:
            raise Unavailable("Unlimited-OCR-Workerprotokoll ungültig") from None
        if not response.get("ok"):
            raise Unavailable(response.get("error", "Unlimited-OCR fehlgeschlagen"))
        return response["result"]

    def extract(self, image, data=None):
        started = time.perf_counter()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        with self.progress.activity("Unlimited-OCR: Seite lokal erkennen"):
            result = self.request(
                dict(command="recognize", png=base64.b64encode(buffer.getvalue()).decode("ascii"))
            )
        self.calls += 1
        self._resources = result["resources"]
        clean = clean_text(result["raw_response"])
        people, evidence, notes = ([], [], [])
        if self.options.extraction == "table":
            people, evidence, notes = extract_tables(clean)
        elif self.options.extraction == "llm":
            notes = ["Lokale LLM-Zellzuordnung folgt nach Entladen von Unlimited-OCR"]
            self.progress.log("OCR-Text gesichert; Teilnehmer-Zuordnung folgt als separater lokaler LLM-Schritt")
        else:
            notes = [
                "Reine OCR-Ausgabe; keine strukturierte Teilnehmerextraktion oder Signaturklassifikation"
            ]
        result.update(
            clean_text=clean,
            plain_text=plain_text(clean),
            row_evidence=evidence,
            review_notes=notes,
            parse_status="valid" if self.options.extraction == "table" else "not_attempted",
            output_kind="ocr_text" if self.options.extraction == "none" else "structured",
        )
        status = (
            "partial"
            if result["output_budget_reached"]
            or self.options.extraction == "llm"
            or (self.options.extraction == "table" and (not people or notes))
            else "success"
        )
        return people, [result], status, time.perf_counter() - started

    def resources(self):
        return dict(self._resources, runtime_log=str(self.log_path), calls=self.calls)

    def close(self):
        if hasattr(self, "process"):
            if self.process.poll() is None:
                try:
                    self.process.stdin.write('{"command":"close"}\n')
                    self.process.stdin.flush()
                    self.process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    self.process.kill()
                    self.process.wait(timeout=10)
            self.process.stdin.close()
            self.process.stdout.close()
            self._reader.join(timeout=2)
        if hasattr(self, "_log"):
            self._log.close()


def identity(spec):
    options = UnlimitedOptions.model_validate(spec.options)
    python, worker, lock = runtime_paths(options)
    installed = None
    if python.is_file():
        script = (
            "import json,importlib.metadata as m; "
            "print(json.dumps({n:m.version(n) for n in "
            "['torch','torchvision','transformers','huggingface-hub','pillow','safetensors']}))"
        )
        try:
            installed = json.loads(
                subprocess.run(
                    [str(python), "-c", script], capture_output=True, text=True, check=True, timeout=30
                ).stdout
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            raise Unavailable(
                "Unlimited-OCR-Laufzeit unvollständig; uv sync --locked --project unlimited_ocr_runtime"
            ) from None
    return dict(
        **local_model_identity(spec),
        runtime_python=str(python),
        runtime_lock=file_hash(lock) if lock.is_file() else None,
        worker=file_hash(worker),
        main_packages={name: importlib.metadata.version(name) for name in ("pymupdf", "pillow")},
        runtime_packages=installed,
        output_kind="ocr_text" if options.extraction == "none" else "structured",
    )
