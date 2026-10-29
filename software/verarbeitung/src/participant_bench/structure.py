"""Local page/table adapters; separate workers isolate Paddle and Docling dependencies and GPU memory."""

import base64
import importlib.metadata
import importlib.util
import io
import json
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pymupdf

from .config import structure_settings
from .doctor import tesseract_command
from .io import digest, file_hash, read_json, write_json
from .models import Unavailable
from .progress import Progress
from .unlimited_tables import extract_tables


def runtime_paths(method, settings):
    method = "paddle_structure" if method in ("paddle_llm", "ocr_vlm") else method
    software = Path(__file__).resolve().parents[3]
    project = software / ("paddle_structure_runtime" if method == "paddle_structure" else "docling_runtime")
    python = Path(settings.runtime_python) if settings.runtime_python else (
        project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    return python.resolve(), software / "structure_runtime", project / "uv.lock"


def model_manifest(root, verify=False):
    path = root / "models-manifest.json"
    if not path.is_file():
        raise Unavailable("Strukturmodelle fehlen; zuerst setup-structures --download ausführen")
    manifest = read_json(path)
    if not manifest.get("files"):
        raise Unavailable("Leeres Strukturmodell-Manifest")
    for name, expected in manifest["files"].items():
        source = (root / name).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file() or source.is_symlink():
            raise Unavailable("Lokaler Strukturmodellpfad fehlt oder ist ungültig")
        if verify and file_hash(source) != expected:
            raise Unavailable("Prüfsumme eines Strukturmodells stimmt nicht; Modelle erneut bereitstellen")
    return manifest


def structure_identity(method, config):
    settings = structure_settings(config, method)
    method = "paddle_structure" if method in ("paddle_llm", "ocr_vlm") else method
    python, source, lock = runtime_paths(method, settings)
    if not python.is_file() or not lock.is_file():
        raise Unavailable(f"Isolierte Laufzeit fehlt: uv sync --locked --project {lock.parent.name}")
    manifest = model_manifest(Path(settings.models_dir))
    packages = (["paddleocr", "paddlex", "paddlepaddle-gpu", "pillow"] if method == "paddle_structure" else
                ["docling", "docling-core", "docling-ibm-models", "torch", "transformers", "pillow"])
    script = "import json,importlib.metadata as m; print(json.dumps({n:m.version(n) for n in " + repr(packages) + "}))"
    try:
        installed = json.loads(subprocess.run([str(python), "-c", script], capture_output=True,
                                             text=True, check=True, timeout=30).stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise Unavailable(f"Strukturlaufzeit unvollständig; uv sync --locked --project {lock.parent.name}") from None
    dependencies = {}
    if method == "docling":
        from .ocr import OCR

        try:
            dependencies["ocr"] = OCR(config).identity
            dependencies["ocr_image_preprocessing"] = file_hash(Path(__file__).with_name("image_preprocessing.py"))
        except (OSError, RuntimeError) as exc:
            raise Unavailable("Docling benötigt lokale Tesseract-Sprachdaten: " + str(exc)) from None
    elif settings.device == "cuda" and os.name == "nt":
        try:
            dependencies["cuda_dll_provider"] = importlib.metadata.version("torch")
        except importlib.metadata.PackageNotFoundError:
            raise Unavailable("Windows Paddle CUDA benötigt die CUDA-DLLs des Hauptprojekts; uv sync --extra models") from None
    return dict(backend="local", engine=method, models=digest(manifest), runtime_python=str(python),
                runtime_lock=file_hash(lock), runtime_packages=installed,
                worker={p.name: file_hash(p) for pattern in ("*.py", "*_sources.json") for p in source.glob(pattern)},
                dependencies=dependencies)


def single_page_pdf(page):
    """Retain native PDF text and apply only additional analysis rotations; originals remain untouched."""
    if page.get("source_kind", "pdf") != "pdf":
        return None
    with pymupdf.open(page["source_path"]) as source, pymupdf.open() as target:
        number = page["page_number"] - 1
        target.insert_pdf(source, from_page=number, to_page=number)
        extra = page.get("additional_rotation_clockwise", 0) + page.get("curation_rotation_clockwise", 0)
        target[0].set_rotation((target[0].rotation + extra) % 360)
        return target.tobytes()


def docling_page_pdf(page, scan_input="rendered"):
    """Preserve native text; flatten textless scan mosaics for whole-page OCR.

    None asks the adapter to build a lossless single-image PDF. Tiled
    scans otherwise reach Docling as hundreds of unrelated OCR crops.
    """
    data = single_page_pdf(page)
    if data is not None and scan_input == "rendered":
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if not document[0].get_text().strip():
                return None
    return data


def lossless_image_pdf(image, dpi):
    """Package the oriented analysis pixels without JPEG recompression."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    with pymupdf.open() as document:
        page = document.new_page(width=image.width * 72 / dpi, height=image.height * 72 / dpi)
        page.insert_image(page.rect, stream=buffer.getvalue())
        return document.tobytes(deflate=True)


def recognition_key(identity, settings, config, page, method):
    return digest(dict(identity=identity, settings=settings.model_dump(), cache_protocol="structure-recognition-timing-v2",
        image=page["run_image_sha256"], document=page["document_id"], page=page["page_number"],
        rotation=[page.get("additional_rotation_clockwise", 0), page.get("curation_rotation_clockwise", 0)],
        ocr=config.ocr.model_dump() if method == "docling" else None))


def page_cache(path, key):
    try:
        result = read_json(path) if path.is_file() else None
        valid = (isinstance(result, dict) and result.get("cache_key") == key
                 and isinstance(result.get("tables"), list)
                 and all(isinstance(table, dict) and isinstance(table.get("html"), str) for table in result["tables"])
                 and isinstance(result.get("markdown"), str) and isinstance(result.get("plain_text"), str))
        return result if valid else None
    except (ValueError, OSError, AttributeError):
        return None


def recognition_cache_reader(method, config):
    """Read a validated warm OCR cache without allocating a second GPU worker."""
    settings, identity = structure_settings(config, method), structure_identity(method, config)
    engine = "paddle_structure" if method in ("paddle_llm", "ocr_vlm") else method
    def read(page):
        key = recognition_key(identity, settings, config, page, engine)
        result = page_cache(Path(config.cache_dir) / engine / (key + ".json"), key)
        return dict(result, cache_hit=True, cache_key=key, recognizer_identity=identity) if result is not None else None
    return read


class StructureModel:
    def __init__(self, method, config, progress=None):
        self.method, self.config = ("paddle_structure" if method in ("paddle_llm", "ocr_vlm") else method), config
        self.progress = progress or Progress(enabled=False)
        self.identity = structure_identity(method, config)
        self.settings = structure_settings(config, method)
        method = self.method
        self.mapping_context = {}
        model_manifest(Path(self.settings.models_dir), verify=True)
        self.python, source, _ = runtime_paths(method, self.settings)
        self.cache = Path(config.cache_dir) / method
        self.cache.mkdir(parents=True, exist_ok=True)
        self.log_path = self.cache / (uuid.uuid4().hex + ".log")
        self.process = self.reader = self.log = None
        self.calls, self._resources = 0, {}
        settings = self.settings.model_dump()
        settings["models_dir"] = str(Path(settings["models_dir"]).resolve())
        settings["cache_dir"] = str(self.cache.resolve())
        if method == "paddle_structure" and self.settings.device == "cuda" and os.name == "nt":
            torch_spec = importlib.util.find_spec("torch")
            if torch_spec and torch_spec.origin:
                settings["cuda_library_dir"] = str(Path(torch_spec.origin).parent / "lib")
        if method == "docling":
            settings.update(tesseract_command=tesseract_command(config), languages=config.ocr.languages,
                            tesseract_psm=config.ocr.psm, remove_grid_lines=config.ocr.remove_grid_lines,
                            image_preprocessing_source=str(Path(__file__).with_name("image_preprocessing.py")))
        self.log = self.log_path.open("w", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                [str(self.python), "-u", str(source / "worker.py")], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self.log, text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.responses = queue.Queue()
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            with self.progress.activity(f"{method}: lokale OCR-/Tabellenmodelle laden ({self.settings.device})"):
                self._resources = self.request(dict(command="init", method=method, settings=settings))
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.responses.put(line)
        finally:
            self.responses.put(None)

    def request(self, request):
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            line = self.responses.get(timeout=self.settings.timeout_seconds)
            if line is None:
                raise Unavailable(f"{self.method}: Worker beendet; Protokoll: {self.log_path}")
            response = json.loads(line)
            if not response.get("ok"):
                raise Unavailable(response.get("error", "Lokale Tabellenanalyse fehlgeschlagen")
                                  + f"; Protokoll: {self.log_path}")
            return response["result"]
        except (BrokenPipeError, OSError, queue.Empty, ValueError):
            if self.process.poll() is None:
                self.process.kill()
            raise Unavailable(f"{self.method}: Workerprotokoll oder Zeitlimit; lokales Laufzeitprotokoll prüfen") from None

    def extract_page(self, image, page):
        started = time.perf_counter()
        key = recognition_key(self.identity, self.settings, self.config, page, self.method)
        cache_path = self.cache / (key + ".json")
        result = page_cache(cache_path, key)
        cached = result is not None
        if not cached:
            recognition_started = time.perf_counter()
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            pdf_bytes = docling_page_pdf(page, self.settings.scan_input) if self.method == "docling" else None
            flattened = self.method == "docling" and pdf_bytes is None
            if flattened:
                pdf_bytes = lossless_image_pdf(image, self.config.pdf.dpi)
            with self.progress.activity(f"{self.method}: Seite und Tabellenstruktur lokal auslesen"):
                result = self.request(dict(command="recognize", png=base64.b64encode(buffer.getvalue()).decode(),
                                           pdf=base64.b64encode(pdf_bytes).decode() if pdf_bytes else None))
            self.calls += 1
            result["recognition_seconds"] = time.perf_counter() - recognition_started
            if flattened:
                result["source_kind"] = "rendered_page_pdf_lossless"
            self._resources.update(result.pop("resources", {}))
            write_json(cache_path, dict(result, cache_key=key))
            self.enforce_limit()
        else:
            self.progress.log(f"{self.method}: Seitenanalyse aus lokalem Cache übernommen")
        html = "\n".join(table["html"] for table in result["tables"])
        result = dict(result, organization_header_aliases=self.settings.organization_header_aliases)
        # This mapping uses explicit printed headers only; it never calls an LLM or splits guessed names.
        if self.method == "docling" and self.settings.extraction == "table":
            from .table_mapping import VERSION, extract_docling

            if self.settings.mapping == "structured":
                from .structured_mapping import VERSION, extract_structured

                people, evidence, notes, context = extract_structured(result, self.mapping_context.get(page["document_id"]))
            else:
                people, evidence, notes, context = extract_docling(result, self.mapping_context.get(page["document_id"]))
            self.mapping_context[page["document_id"]] = context
            result = dict(result, mapping_version=VERSION, table_mapping_context=context,
                          assignment_backend="deterministic_headers")
        else:
            people, evidence, notes = extract_tables(html)
        result = dict(result, row_evidence=evidence, review_notes=notes, cache_hit=cached,
                      cache_key=key, table_count=len(result["tables"]), recognizer_identity=self.identity)
        if not people:
            notes.append("Tabellen und vollständiger Seitentext erhalten; semantische Feldzuordnung manuell prüfen")
        if self.settings.extraction == "llm":
            people = []  # Never substitute a provisional mapping for the requested LLM pipeline.
            notes.append("Lokale LLM-Zellzuordnung folgt nach Entladen des Strukturmodells")
        # Cell matching is auditable evidence, not proof of correct OCR/semantics.
        return people, result, "partial", time.perf_counter() - started

    def restore_mapping(self, page, raw):
        context = raw.get("structure", {}).get("table_mapping_context")
        if context:
            self.mapping_context[page["document_id"]] = context

    def enforce_limit(self):
        # Only generated top-level page cache files; SDK files, logs and originals are excluded.
        files = [path for path in self.cache.glob("*.json")
                 if not path.is_symlink() and re.fullmatch(r"[0-9a-f]{64}", path.stem)]
        files.sort(key=lambda path: path.stat().st_mtime)
        size = sum(path.stat().st_size for path in files)
        for path in files:
            if size <= self.config.cache_max_gb * 1024**3:
                break
            size -= path.stat().st_size
            path.unlink()

    def resources(self):
        return dict(self._resources, calls=self.calls, runtime_log=str(self.log_path))

    def close(self):
        if self.process:
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
            if self.reader:
                self.reader.join(timeout=2)
        if self.log:
            self.log.close()
