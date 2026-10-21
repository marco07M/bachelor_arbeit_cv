import importlib.metadata
import platform
import shutil
import subprocess
from pathlib import Path

import psutil


def tesseract_command(config) -> str:
    if config.ocr.command != "auto":
        return config.ocr.command
    candidates = [
        shutil.which("tesseract"),
        ".tools/ocr/tesseract.exe",
        ".tools/ocr/Library/bin/tesseract.exe",
        "C:/Program Files/Tesseract-OCR/tesseract.exe",
    ]
    for item in candidates:
        if item and Path(item).is_file():
            return str(Path(item).resolve())
    raise FileNotFoundError("Tesseract fehlt. Siehe uv run python scripts/setup_ocr.py")


def environment(config, check_torch=True):
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage(Path.cwd())
    info = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "ram_total_bytes": memory.total,
        "ram_available_bytes": memory.available,
        "disk_total_bytes": disk.total,
        "disk_free_bytes": disk.free,
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "warnings": [],
        "gpu": [],
        "backend": "not checked",
    }
    uv_executable = shutil.which("uv") or str(Path(".tools/uv.exe").resolve())
    try:
        info["uv_version"] = subprocess.run(
            [uv_executable, "--version"], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        info["uv_version"] = "not found"
    if platform.system() == "Windows":
        import winreg

        adapters = []
        registry_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as registry:
                for index in range(winreg.QueryInfoKey(registry)[0]):
                    name = winreg.EnumKey(registry, index)
                    if not name.isdigit():
                        continue
                    try:
                        with winreg.OpenKey(registry, name) as adapter:
                            adapters.append(
                                {
                                    key: winreg.QueryValueEx(adapter, value)[0]
                                    for key, value in (
                                        ("name", "DriverDesc"),
                                        ("vendor", "ProviderName"),
                                        ("driver", "DriverVersion"),
                                    )
                                }
                            )
                    except OSError:
                        continue
        except OSError as exc:
            info["warnings"].append(f"Display adapter inventory unavailable: {exc}")
        info["registered_display_adapters"] = adapters
        info["display_inventory_scope"] = (
            "Windows display driver entries; usable CUDA devices listed separately"
        )
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                index, name, total, free, driver = [s.strip() for s in line.split(",")]
                info["gpu"].append(
                    dict(
                        index=int(index),
                        vendor="NVIDIA",
                        name=name,
                        total_mib=int(total),
                        free_mib=int(free),
                        driver=driver,
                    )
                )
        else:
            info["warnings"].append(
                "nvidia-smi meldet keine NVIDIA-GPU; andere Hersteller nicht ausgeschlossen"
            )
    except (OSError, subprocess.TimeoutExpired):
        info["warnings"].append("nvidia-smi nicht verfügbar; GPU-Hersteller nicht bestimmt")
    if check_torch and any(spec.backend == "local" for spec in config.models.values()):
        try:
            import torch

            info["torch_version"] = torch.__version__
            info["torch_cuda_build"] = torch.version.cuda
            info["backend"] = "cuda" if torch.cuda.is_available() else "cpu"
            if torch.cuda.is_available():
                info["cuda_device_count"] = torch.cuda.device_count()
                info["torch_gpus"] = [
                    {
                        "name": torch.cuda.get_device_name(i),
                        "free_bytes": torch.cuda.mem_get_info(i)[0],
                        "total_bytes": torch.cuda.mem_get_info(i)[1],
                    }
                    for i in range(torch.cuda.device_count())
                ]
            if getattr(torch.version, "hip", None):
                info["backend"] = "rocm"
            if hasattr(torch, "xpu") and torch.xpu.is_available():
                info["backend"] = "xpu (nicht durch diesen Modelladapter unterstützt)"
            if info["backend"] == "cpu":
                info["warnings"].append("Kein nutzbares CUDA-Backend; CPU-Modus nur explizit konfigurieren")
        except (ImportError, OSError, RuntimeError) as exc:
            info["backend"] = "unavailable"
            info["warnings"].append(
                f"PyTorch/Backend nicht nutzbar: {exc}; uv sync --locked --extra models prüfen"
            )
    try:
        command = tesseract_command(config)
        result = subprocess.run([command, "--list-langs"], capture_output=True, text=True, timeout=15)
        languages = result.stdout.splitlines()[1:]
        version = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15)
        info["tesseract"] = {
            "command": command,
            "version": version.stdout.splitlines()[0],
            "languages": languages,
        }
        for language in config.ocr.languages.split("+") + ["osd"]:
            if language not in languages:
                info["warnings"].append(f"Tesseract-Sprachdaten fehlen: {language}")
    except (OSError, subprocess.TimeoutExpired, IndexError) as exc:
        info["warnings"].append(str(exc))
    info["models"] = {}
    for method, model in config.models.items():
        from .models import Unavailable, model_identity

        try:
            info["models"][method] = dict(status="available", **model_identity(model))
        except (Unavailable, ValueError, KeyError) as exc:
            info["models"][method] = {"status": "unavailable", "reason": str(exc)}
            info["warnings"].append(f"{method}: {exc}")
        if model.backend == "api":
            from .api_models import missing_environment

            missing = missing_environment(model)
            info["models"][method]["missing_environment"] = missing
            info["models"][method]["connection_verified"] = False
            if missing:
                info["models"][method]["status"] = "unconfigured"
            continue
        if model.device != "cpu" and info.get("gpu"):
            free = info["gpu"][0]["free_mib"] / 1024
            if free < model.gpu_memory_gib + 2:
                info["warnings"].append(f"{method}: GPU-Budget plus 2 GiB Reserve über freiem Speicher")
        if memory.available < (model.cpu_memory_gib + 4) * 1024**3:
            info["warnings"].append(f"{method}: CPU-Offload-Budget plus Reserve über verfügbarem RAM")
    return info
