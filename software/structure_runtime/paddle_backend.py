"""PP-StructureV3 using explicit local German/Latin OCR and table model directories."""

import json
import os
from pathlib import Path

# Names and all enabled model paths are explicit; disabled modules cannot trigger downloads.
PADDLE_MODELS = {
    "layout_detection": "PP-DocLayout_plus-L",
    "text_detection": "PP-OCRv5_server_det",
    "text_recognition": "latin_PP-OCRv5_mobile_rec",
    "textline_orientation": "PP-LCNet_x1_0_textline_ori",
    "table_classification": "PP-LCNet_x1_0_table_cls",
    "wired_table_structure_recognition": "SLANeXt_wired",
    "wireless_table_structure_recognition": "SLANet_plus",
    "wired_table_cells_detection": "RT-DETR-L_wired_table_cell_det",
    "wireless_table_cells_detection": "RT-DETR-L_wireless_table_cell_det",
    "table_orientation_classify": "PP-LCNet_x1_0_doc_ori",
}


class PaddleBackend:
    def __init__(self, settings):
        os.environ["PADDLE_PDX_CACHE_HOME"] = settings["cache_dir"]
        self._dll_handles = []
        if os.name == "nt" and settings["device"] == "cuda" and settings.get("cuda_library_dir"):
            import ctypes

            directory = Path(settings["cuda_library_dir"])
            self._dll_handles.append(os.add_dll_directory(str(directory)))
            # cuDNN lazily loads component DLLs via native LoadLibrary; enable user DLL directories too.
            if not ctypes.windll.kernel32.SetDefaultDllDirectories(0x00001000):
                raise OSError("Cannot configure process-local CUDA DLL search")
            # Reuse the installed CUDA 12.6/cuDNN 9 runtime, without importing PyTorch into Paddle.
            for name in ("cudnn64_9.dll", "cublasLt64_12.dll", "cublas64_12.dll", "cudart64_12.dll"):
                library = directory / name
                if library.is_file():
                    self._dll_handles.append(ctypes.WinDLL(str(library)))
        import paddle
        from paddleocr import PPStructureV3

        device = settings["device"]
        if device == "cuda" and not paddle.device.is_compiled_with_cuda():
            raise RuntimeError("Paddle CUDA build unavailable; install the isolated CUDA runtime")
        self.paddle = paddle
        root = Path(settings["models_dir"])
        models = {}
        for parameter, name in PADDLE_MODELS.items():
            path = root / name
            if not (path / "inference.yml").is_file():
                raise FileNotFoundError("Local Paddle model incomplete; run setup-structures")
            models[parameter + "_model_name"] = name
            models[parameter + "_model_dir"] = str(path)
        self.pipeline = PPStructureV3(
            **models, device="gpu:0" if device == "cuda" else "cpu",
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=True, use_table_recognition=True,
            use_formula_recognition=False, use_chart_recognition=False,
            use_seal_recognition=False, use_region_detection=False,
            enable_mkldnn=False,
        )
        self.device = device

    def recognize(self, image, pdf_bytes=None):
        import numpy as np

        results = list(self.pipeline.predict(np.array(image.convert("RGB"))[:, :, ::-1]))
        if len(results) != 1:
            raise RuntimeError("Expected one Paddle page result")
        raw = results[0].json
        raw = json.loads(raw) if isinstance(raw, str) else raw
        native = raw.get("res", raw)
        tables = [{"html": table["pred_html"], "native": table}
                  for table in native.get("table_res_list", []) if table.get("pred_html")]
        blocks = native.get("parsing_res_list", [])
        markdown = "\n".join(str(block.get("block_content", "")) for block in blocks)
        # Layout detection can miss a continuation table while full-page OCR
        # still reads its rows. Never discard those recognized words.
        text = "\n".join(native.get("overall_ocr_res", {}).get("rec_texts", [])) or markdown
        return dict(tables=tables, markdown=markdown or text, plain_text=text, native=native,
                    source_kind="rendered_page", structure_engine="PP-StructureV3")

    def resources(self):
        result = {"device": self.device}
        if self.device == "cuda":
            result["peak_gpu_allocated_bytes"] = self.paddle.device.cuda.max_memory_allocated()
            result["peak_gpu_reserved_bytes"] = self.paddle.device.cuda.max_memory_reserved()
        return result
