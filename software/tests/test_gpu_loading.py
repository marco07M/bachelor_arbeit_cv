"""Enforce explicit CUDA placement and the smaller default text model."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from participant_bench.config import ModelConfig, load_config
from participant_bench.models import LocalModel, Unavailable, model_load_kwargs


def spec(**changes):
    return ModelConfig(repo="synthetic/model", revision="a" * 40, path="unused", **changes)


def torch_double(available=True, capability=(8, 9)):
    return SimpleNamespace(
        bfloat16="bf16", cuda=SimpleNamespace(
            is_available=lambda: available, get_device_capability=lambda index: capability,
        ),
    )


def test_cuda_keeps_all_layers_on_gpu_instead_of_auto_offload():
    options = model_load_kwargs(spec(device="cuda"), torch_double(), "vlm")
    assert options["device_map"] == {"": 0}
    assert "max_memory" not in options
    assert options["local_files_only"] and not options["trust_remote_code"]
    assert options["use_safetensors"] and options["low_cpu_mem_usage"]


def test_cpu_offload_remains_explicitly_available_in_auto_mode():
    options = model_load_kwargs(spec(device="auto", gpu_memory_gib=12), torch_double(), "ocr_llm")
    assert options["device_map"] == "auto" and options["max_memory"][0] == "12GiB"
    assert "cpu" in options["max_memory"]
    options = model_load_kwargs(spec(device="cpu"), torch_double(False), "ocr_llm")
    assert options["device_map"] == {"": "cpu"}


@pytest.mark.parametrize("device", ["cuda", "auto"])
def test_cuda_request_does_not_silently_fall_back_to_cpu(device):
    with pytest.raises(Unavailable, match="no CUDA"):
        model_load_kwargs(spec(device=device), torch_double(False), "ocr_llm")


@pytest.mark.parametrize("device", ["auto", "cpu"])
def test_int8_configuration_requires_explicit_cuda(device):
    with pytest.raises(ValidationError, match="ohne CPU-Offload"):
        spec(device=device, quantization="int8")


def test_int8_loads_original_checkpoint_on_gpu_without_cpu_offload(monkeypatch):
    monkeypatch.setitem(sys.modules, "bitsandbytes", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(BitsAndBytesConfig=lambda **kw: kw))
    options = model_load_kwargs(spec(device="cuda", quantization="int8"), torch_double(), "ocr_llm")
    assert options["device_map"] == {"": 0}
    assert options["quantization_config"] == {
        "load_in_8bit": True, "llm_int8_threshold": 6.0, "llm_int8_enable_fp32_cpu_offload": False,
    }
    with pytest.raises(Unavailable, match="Compute Capability"):
        model_load_kwargs(spec(device="cuda", quantization="int8"), torch_double(capability=(6, 1)), "ocr_llm")


def test_missing_int8_runtime_has_setup_instruction_and_no_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "bitsandbytes", None)
    with pytest.raises(Unavailable, match="uv sync --locked --extra models"):
        model_load_kwargs(spec(device="cuda", quantization="int8"), torch_double(), "ocr_llm")


def test_int8_does_not_change_vlm_precision():
    with pytest.raises(Unavailable, match="VLM bleibt in BF16"):
        model_load_kwargs(spec(device="cuda", quantization="int8"), torch_double(), "vlm")


@pytest.mark.parametrize("filename", [
    "local.yaml", "imported.yaml", "benchmark-unlimited.yaml", "ocr-sparse.yaml",
    "unlimited-ocr-llm.yaml", "paddle-structure.yaml", "docling.yaml", "structure-models.yaml",
])
def test_active_configs_use_unified_four_b_instruct_with_gpu_loading(filename):
    config = load_config(Path("configs") / filename)
    llm, vlm = config.models["ocr_llm"], config.models["vlm"]
    assert llm.repo == "Qwen/Qwen3-4B-Instruct-2507" and llm.path == "models/qwen3-4b-instruct-2507"
    assert llm.revision == "cdbee75f17c01a7cc42f958dc650907174af0554"
    assert llm.quantization == "none" and llm.dtype == "bfloat16" and llm.device == "cuda"
    assert llm.prefill_chunk_size == 1024
    assert llm.max_new_tokens == 8192
    assert vlm.repo == "Qwen/Qwen3-VL-4B-Instruct" and vlm.path == "models/qwen3-vl-4b"
    assert vlm.revision == "ebb281ec70b05090aa6165b016eac8ec08e71b17"
    assert vlm.quantization == "none" and vlm.device == "cuda"


def test_initialization_failure_restores_cuda_allocator_limit(monkeypatch):
    restored = []

    def failed_initialization(self, *args):
        self.cuda = True
        self.torch = SimpleNamespace(
            _C=SimpleNamespace(_cuda_clearCublasWorkspaces=lambda: restored.append("workspaces cleared")),
            cuda=SimpleNamespace(
                synchronize=lambda: restored.append("synchronized"),
                empty_cache=lambda: restored.append("cache cleared"),
                set_per_process_memory_fraction=lambda value, index: restored.append((value, index)),
            ),
        )
        self._previous_cuda_memory_fraction = 1.0
        self.model, self.processor = object(), object()
        raise RuntimeError("synthetic loading failure")

    monkeypatch.setattr(LocalModel, "_initialize", failed_initialization)
    with pytest.raises(RuntimeError, match="synthetic loading failure"):
        LocalModel("ocr_llm", None)
    assert restored == ["synchronized", "workspaces cleared", "cache cleared", (1.0, 0)]


@pytest.mark.parametrize("chunk_size", [1024, None])
def test_chunked_prefill_preserves_every_input_token(chunk_size):
    torch = pytest.importorskip("torch")
    original = torch.arange(1500).reshape(1, -1)
    received = {}

    class Batch(dict):
        def to(self, device):
            return self

    def generate(**kwargs):
        received.update(kwargs)
        return torch.cat((kwargs["input_ids"], torch.zeros((1, 1), dtype=torch.long)), dim=1)

    model = object.__new__(LocalModel)
    model.method, model.cuda, model.torch = "ocr_llm", False, torch
    model.spec = spec(device="cuda", prefill_chunk_size=chunk_size)
    model.processor = SimpleNamespace(
        apply_chat_template=lambda *args, **kwargs: "full prompt", decode=lambda *args, **kwargs: "{}",
    )
    # SimpleNamespace has no __call__; use a small tokenizer double.
    class Tokenizer:
        apply_chat_template = staticmethod(model.processor.apply_chat_template)
        decode = staticmethod(model.processor.decode)

        def __call__(self, *args, **kwargs):
            return Batch(input_ids=original)

    model.processor = Tokenizer()
    model.model = SimpleNamespace(device="cpu", generate=generate)
    _, metadata = model.generate("all OCR words")
    assert torch.equal(received["input_ids"], original)
    assert received.get("prefill_chunk_size") == chunk_size
    assert metadata["input_tokens"] == 1500 and metadata["output_tokens"] == 1
