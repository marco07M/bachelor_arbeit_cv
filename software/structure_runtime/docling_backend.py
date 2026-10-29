"""Native single-page PDF parsing plus local OCR and TableFormer, without a VLM or LLM."""

import importlib.util
import io


def configure_ocr_images(model_class, cleaner):
    """Adapt the pinned Docling CLI hook; table/layout rendering stays untouched."""
    from PIL import Image

    original = model_class._run_tesseract

    def run(model, filename, osd):
        with Image.open(filename) as image:
            dpi = image.info.get("dpi", (216, 216))
            cleaned = cleaner(image)
        try:
            cleaned.save(filename, format="PNG", dpi=dpi)
        finally:
            cleaned.close()
        return original(model, filename, osd)

    model_class._run_tesseract = run


class DoclingBackend:
    def __init__(self, settings):
        import torch
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            OcrMode,
            PdfPipelineOptions,
            TableFormerMode,
            TesseractCliOcrOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        if settings.get("remove_grid_lines"):
            from docling.models.stages.ocr.tesseract_ocr_cli_model import TesseractOcrCliModel

            source = settings["image_preprocessing_source"]
            spec = importlib.util.spec_from_file_location("participant_image_preprocessing", source)
            transforms = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(transforms)
            configure_ocr_images(TesseractOcrCliModel, transforms.remove_grid_lines)

        self.torch, self.device = torch, settings["device"]
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Docling CUDA unavailable; use device: cpu explicitly")
        options = PdfPipelineOptions(
            artifacts_path=settings["models_dir"], enable_remote_services=False,
            allow_external_plugins=False, do_ocr=True, do_table_structure=True,
            generate_parsed_pages=True,
            do_picture_classification=False, do_picture_description=False,
            do_code_enrichment=False, do_formula_enrichment=False,
            ocr_options=TesseractCliOcrOptions(
                lang=settings["languages"].split("+"), tesseract_cmd=settings["tesseract_command"],
                mode=OcrMode.FULL_PAGE if settings.get("force_full_page_ocr", False) else OcrMode.DEFAULT,
                scale=settings.get("ocr_scale", 3.0), psm=settings.get("tesseract_psm"),
            ),
            accelerator_options=AcceleratorOptions(
                device=AcceleratorDevice.CUDA if self.device == "cuda" else AcceleratorDevice.CPU,
            ),
        )
        options.table_structure_options.mode = TableFormerMode(settings["table_mode"])
        options.table_structure_options.do_cell_matching = settings.get("do_cell_matching", True)
        self.effective_options = dict(ocr_backend="tesseract_cli", do_ocr=options.do_ocr,
            ocr_mode=options.ocr_options.mode.value, ocr_scale=options.ocr_options.scale,
            ocr_languages=options.ocr_options.lang, ocr_psm=options.ocr_options.psm,
            table_mode=options.table_structure_options.mode.value,
            do_cell_matching=options.table_structure_options.do_cell_matching,
            remove_grid_lines=bool(settings.get("remove_grid_lines")),
            embedded_text_policy="OCR mode DEFAULT keeps native text; FULL_PAGE explicitly re-recognizes the page")
        self.converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        # Initialize eagerly so timing separates model loading and page inference.
        self.converter.initialize_pipeline(InputFormat.PDF)

    def recognize(self, image, pdf_bytes=None):
        from docling.datamodel.base_models import DocumentStream

        if pdf_bytes is None:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PDF", resolution=220)
            pdf_bytes = buffer.getvalue()
            source_kind = "rendered_page_pdf"
        else:
            source_kind = "native_single_page_pdf"
        result = self.converter.convert(DocumentStream(name="page.pdf", stream=io.BytesIO(pdf_bytes)), raises_on_error=True)
        document = result.document
        tables = [{"html": table.export_to_html(doc=document),
                   "native": table.model_dump(mode="json")} for table in document.tables]
        # Keep the OCR/native text boxes before TableFormer merges them into
        # cells. A single merged header must not destroy its column positions.
        ocr_cells = []
        for page in result.pages:
            for index, cell in enumerate(page.cells):
                ocr_cells.append(dict(text=cell.text, bbox=cell.rect.to_bounding_box().model_dump(mode="json"),
                                      confidence=cell.confidence, from_ocr=cell.from_ocr,
                                      native_ref=f"pages/{page.page_no}/cells/{index}"))
        raw_text = "\n".join(cell["text"] for cell in ocr_cells)
        return dict(tables=tables, markdown=document.export_to_markdown(),
                    plain_text=raw_text or document.export_to_text(), native=document.export_to_dict(),
                    ocr_cells=ocr_cells,
                    source_kind=source_kind, structure_engine="TableFormer", effective_options=self.effective_options,
                    ocr_statistics=dict(cells=len(ocr_cells), from_ocr=sum(bool(c["from_ocr"]) for c in ocr_cells),
                                        from_pdf=sum(not bool(c["from_ocr"]) for c in ocr_cells)))

    def resources(self):
        result = {"device": self.device}
        if self.device == "cuda":
            self.torch.cuda.synchronize()
            result["peak_gpu_allocated_bytes"] = self.torch.cuda.max_memory_allocated()
            result["peak_gpu_reserved_bytes"] = self.torch.cuda.max_memory_reserved()
        return result
