"""Persistent local JSON-lines worker. Never downloads models or executes checkpoint Python code."""

import base64
import contextlib
import importlib.metadata
import io
import json
import os
import platform
import sys
import time

for name in (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_HUB_DISABLE_TELEMETRY",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN",
):
    os.environ[name] = "1"


class Runtime:
    def __init__(self, request):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA ist nicht verfügbar; keine automatische CPU-Inferenz")
        self.torch = torch
        self.options = request["options"]
        requested = self.options.get("precision", "auto")
        bf16 = torch.cuda.is_bf16_supported()
        if requested == "bfloat16" and not bf16:
            raise RuntimeError("BF16 wird von dieser GPU nicht unterstützt; FP16 explizit konfigurieren")
        self.precision = (
            "bfloat16" if requested == "auto" and bf16 else "float16" if requested == "auto" else requested
        )
        self.dtype = getattr(torch, self.precision)
        free, total = torch.cuda.mem_get_info()
        if free < self.options.get("min_free_gib", 9) * 1024**3:
            raise RuntimeError("Zu wenig freier GPU-Speicher; andere GPU-Programme schließen")
        torch.manual_seed(request["seed"])
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.perf_counter()
        path = request["model_path"]
        self.processor = AutoProcessor.from_pretrained(path, local_files_only=True, trust_remote_code=False)
        self.model, loading = AutoModelForImageTextToText.from_pretrained(
            path,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            dtype=self.dtype,
            device_map={"": "cuda:0"},
            attn_implementation=self.options.get("attention", "sdpa"),
            output_loading_info=True,
        )
        if any(
            loading.get(key) for key in ("missing_keys", "mismatched_keys", "unexpected_keys", "error_msgs")
        ):
            del self.model
            raise RuntimeError(
                "Checkpoint passt nicht vollständig zur nativen Implementierung; keine Inferenz mit zufälligen Gewichten"
            )
        self.model.eval()
        torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - started
        self.max_tokens = request["max_new_tokens"]
        self.calls = 0
        self.warmup_seconds = 0.0
        self.warmup_calls = 0
        self.hardware = dict(
            os=platform.platform(),
            python=platform.python_version(),
            packages={
                name: importlib.metadata.version(name)
                for name in (
                    "torch",
                    "torchvision",
                    "transformers",
                    "huggingface-hub",
                    "pillow",
                    "safetensors",
                )
            },
            gpu=torch.cuda.get_device_name(0),
            total_vram_bytes=total,
            free_vram_before_load=free,
            cuda_build=torch.version.cuda,
            bf16_supported=bf16,
            precision=self.precision,
            native_transformers=True,
            trust_remote_code=False,
        )
        if request.get("warmup"):
            from PIL import Image

            with Image.new("RGB", (256, 256), "white") as image:
                start = time.perf_counter()
                self.generate(image, max_tokens=8)
                self.warmup_seconds = time.perf_counter() - start
                self.warmup_calls = 1
                self.calls = 0

    def resources(self):
        return dict(
            load_seconds=self.load_seconds,
            warmup_seconds=self.warmup_seconds,
            warmup_calls=self.warmup_calls,
            calls=self.calls,
            hardware=self.hardware,
            peak_gpu_allocated_bytes=self.torch.cuda.max_memory_allocated(),
            peak_gpu_reserved_bytes=self.torch.cuda.max_memory_reserved(),
            page_processing="single_page",
            batch_size=1,
        )

    def generate(self, image, max_tokens=None):
        torch = self.torch
        torch.cuda.synchronize()
        started = time.perf_counter()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": self.options.get("prompt", "document parsing.")},
                ],
            }
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            processor_kwargs={"crop_to_patches": self.options.get("crop_to_patches", True)},
        ).to(self.model.device, self.dtype)
        torch.cuda.synchronize()
        preprocessing = time.perf_counter() - started
        input_tokens = inputs["input_ids"].shape[-1]
        limit = max_tokens or self.max_tokens
        if input_tokens + limit > 32768:
            raise RuntimeError("Eingabe plus Ausgabelimit überschreiten den 32768-Token-Kontext")
        started = time.perf_counter()
        self.calls += 1
        with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=self.dtype):
            output = self.model.generate(
                **inputs,
                max_new_tokens=limit,
                do_sample=False,
                no_repeat_ngram_size=self.options.get("no_repeat_ngram_size", 35),
                no_repeat_ngram_window_size=self.options.get("no_repeat_ngram_window_size", 128),
            )
        torch.cuda.synchronize()
        inference = time.perf_counter() - started
        started = time.perf_counter()
        generated = output[0, input_tokens:]
        raw, detections = self.processor.decode(generated, skip_special_tokens=False, return_detections=True)
        clean = self.processor.decode(generated, skip_special_tokens=True)
        eos = self.processor.tokenizer.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        truncated = len(generated) >= limit and (not len(generated) or generated[-1].item() not in eos)
        return dict(
            raw_response=raw,
            clean_text=clean,
            detections=detections,
            input_tokens=input_tokens,
            output_tokens=len(generated),
            output_budget_reached=truncated,
            analyzed_image_size=list(image.size),
            page_processing="single_page",
            batch_size=1,
            timings=dict(
                image_preprocessing_seconds=preprocessing,
                model_inference_seconds=inference,
                decoding_seconds=time.perf_counter() - started,
            ),
            resources=self.resources(),
        )


def main():
    runtime = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if request["command"] == "init":
                    runtime = Runtime(request)
                    result = runtime.resources()
                elif request["command"] == "recognize" and runtime is not None:
                    from PIL import Image

                    with Image.open(io.BytesIO(base64.b64decode(request["png"], validate=True))) as source:
                        with source.convert("RGB") as image:
                            result = runtime.generate(image)
                elif request["command"] == "close":
                    return
                else:
                    raise RuntimeError("Ungültige lokale Worker-Anfrage")
            response = dict(ok=True, result=result)
        except Exception as exc:
            # No document text or raw third-party exception is printed into progress logs.
            message = (
                str(exc)
                if isinstance(exc, RuntimeError)
                and str(exc).startswith(
                    (
                        "CUDA ist",
                        "BF16 wird",
                        "Zu wenig",
                        "Checkpoint passt",
                        "Eingabe plus",
                        "Ungültige lokale",
                    )
                )
                else "Lokale Unlimited-OCR-Verarbeitung fehlgeschlagen: " + type(exc).__name__
            )
            if "out of memory" in str(exc).lower():
                message = "CUDA-Speicher erschöpft. Bildmodus oder Ausgabelimit in einem neuen Lauf explizit reduzieren."
                if runtime is not None:
                    runtime.torch.cuda.empty_cache()
            response = dict(ok=False, error=message)
        print(json.dumps(response, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
