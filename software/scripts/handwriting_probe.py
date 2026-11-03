"""Small local OCR probes on fixed pages, without reference-assisted text selection or model downloads."""

import argparse
import html
import io
import time
from pathlib import Path

import numpy as np
import psutil
import pymupdf
from PIL import Image

from participant_bench.config import load_config
from participant_bench.image_preprocessing import binary, remove_grid_lines
from participant_bench.io import digest, file_hash, read_json, write_csv, write_json
from participant_bench.ocr import OCR, raw_transcript
from participant_bench.structure import StructureModel
from participant_bench.structured_mapping import table_rows

VERSION = "handwriting-observation-probe-v1"


def changed_ink(image):
    """Count removed ink, never label it handwriting damage without an independent mask."""
    cleaned = remove_grid_lines(image)
    before, after = binary(image), binary(cleaned)
    cleaned.close()
    return dict(
        ink_before=int(np.count_nonzero(before)),
        removed_ink=int(np.count_nonzero((before > 0) & (after == 0))),
    )


def rerender(page, dpi):
    with pymupdf.open(page["source_path"]) as pdf:
        pix = pdf[page["page_number"] - 1].get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    rotation = page.get("additional_rotation_clockwise", 0) + page.get("curation_rotation_clockwise", 0)
    return image.rotate(-rotation, expand=True, fillcolor="white") if rotation else image


def run(source, output, structures=False):
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Neuen Ausgabeordner außerhalb des Quelllaufs wählen")
    config = load_config(source / "config.yaml")
    pages = [p for p in read_json(source / "effective_pages.json") if p["include"]]
    hashes = {p: file_hash(p) for p in source.rglob("*") if p.is_file()}
    for page in pages:
        original = Path(page["source_path"])
        if file_hash(original) != page["document_id"]:
            raise ValueError("Original-PDF unterscheidet sich vom eingefrorenen Dokument")
        hashes[original] = page["document_id"]
    output.mkdir(parents=True)
    config.cache_dir = str(output / "cache")
    engine = OCR(config)
    records, transforms = [], []
    variants = [
        ("baseline", dict(remove_grid_lines=True)),
        ("original-no-grid", dict(remove_grid_lines=False)),
        ("sparse-no-grid", dict(psm=11, remove_grid_lines=False)),
        ("gray-contrast", dict(remove_grid_lines=False, preprocessing=dict(grayscale=True, contrast=1.4))),
        ("adaptive", dict(remove_grid_lines=False, preprocessing=dict(threshold="adaptive"))),
        ("denoise", dict(remove_grid_lines=False, preprocessing=dict(denoise=3))),
        ("render-300dpi", dict(remove_grid_lines=False)),
    ]
    frozen_ocr = config.ocr.model_copy(deep=True)

    def recognize(image, candidate, label, page, region=None):
        candidate.cache_dir = config.cache_dir
        engine.config = candidate
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        started = time.perf_counter()
        result = engine.recognize(image, digest(buffer.getvalue().hex()))
        folder = output / label
        write_json(folder / "config.json", candidate.model_dump())
        key = f"p{page['page_number']:04d}" + (f"-r{region}" if region is not None else "")
        write_json(folder / f"{key}.json", result)
        (folder / f"{key}.txt").write_text(raw_transcript(result), encoding="utf-8")
        records.append(
            dict(
                engine="tesseract",
                variant=label,
                document_id=page["document_id"],
                page_number=page["page_number"],
                region=region,
                image_size=list(image.size),
                words=len(result["words"]),
                characters=len(result["text"]),
                cache_hit=result["cache_hit"],
                wall_seconds=time.perf_counter() - started,
                ocr_seconds=result["elapsed_seconds"],
                calls=int(not result["cache_hit"]),
                ram_rss_bytes=psutil.Process().memory_info().rss,
                cer=None,
                wer=None,
                quality_status="not_measured_no_localized_transcript",
            )
        )

    for page in pages:
        path = source / "pages" / f"{page['page_id']}.png"
        if file_hash(path) != page["run_image_sha256"]:
            raise ValueError("Laufbild-Hash stimmt nicht")
        with Image.open(path) as original:
            image = original.convert("RGB")
        transforms.append(dict(page_number=page["page_number"], **changed_ink(image)))
        for label, options in variants:
            candidate = config.model_copy(deep=True)
            candidate.ocr = frozen_ocr.model_copy(deep=True)
            preprocessing = options.get("preprocessing", {})
            for key, value in options.items():
                if key != "preprocessing":
                    setattr(candidate.ocr, key, value)
            for key, value in preprocessing.items():
                setattr(candidate.ocr.preprocessing, key, value)
            print(f"Tesseract: {label}, Seite {page['page_number']}", flush=True)
            high = rerender(page, 300) if label == "render-300dpi" else image
            recognize(high, candidate, label, page)
            if high is not image:
                high.close()
        raw_path = source / "docling" / f"raw-{page['page_id']}.json"
        regions = []
        if raw_path.is_file():
            recognized = read_json(raw_path)["structure"]
            size = recognized.get("native", {}).get("pages", {}).get("1", {}).get("size", {})
            proofs = recognized.get("row_evidence", [])
            start = min((r.get("source_row_index", 0) for r in proofs), default=0)
            for index, table in enumerate(recognized.get("tables", [])):
                rows, _, _ = table_rows(table, index, size)
                for row in rows:
                    if row["row_index"] >= start:
                        regions.extend(
                            c["bbox"]
                            for c in row["cells"]
                            if c.get("bbox") and c["colspan"] == c["rowspan"] == 1
                        )
        for index, box in enumerate(regions[:12]):
            crop = image.crop(
                tuple(
                    round(box[k] * size)
                    for k, size in zip(
                        ("x0", "y0", "x1", "y1"), (image.width, image.height, image.width, image.height)
                    )
                )
            )
            candidate = config.model_copy(deep=True)
            candidate.ocr.psm, candidate.ocr.remove_grid_lines = 7, False
            candidate.ocr.preprocessing = frozen_ocr.preprocessing.model_copy(deep=True)
            recognize(crop, candidate, "cell-psm7", page, index)
            write_json(
                output / "cell-psm7" / f"p{page['page_number']:04d}-r{index}-geometry.json",
                dict(bbox=box, source="frozen_tableformer", ground_truth_used=False),
            )
            crop.close()
        image.close()
    if structures:
        settings = [
            ("paddle-det-3200", "paddle_llm"),
            ("docling-no-grid", "docling"),
            ("docling-full-page", "docling"),
        ]
        for label, method in settings:
            candidate = config.model_copy(deep=True)
            candidate.cache_dir = str(output / "cache")
            if method == "paddle_llm":
                candidate.structures[method].text_det_limit_side_len = 3200
            else:
                candidate.ocr.remove_grid_lines = False
                if label == "docling-full-page":
                    candidate.structures[method].force_full_page_ocr = True
            write_json(output / label / "config.json", candidate.model_dump())
            print(label + ": lokale Struktur-Laufzeit laden", flush=True)
            with_model = StructureModel(method, candidate)
            try:
                for page in pages:
                    with Image.open(source / "pages" / f"{page['page_id']}.png") as image:
                        started = time.perf_counter()
                        _, result, _, _ = with_model.extract_page(image, page)
                    write_json(output / label / f"p{page['page_number']:04d}.json", result)
                    records.append(
                        dict(
                            engine=method,
                            variant=label,
                            document_id=page["document_id"],
                            page_number=page["page_number"],
                            words=None,
                            characters=len(result["plain_text"]),
                            tables=len(result["tables"]),
                            wall_seconds=time.perf_counter() - started,
                            cache_hit=result["cache_hit"],
                            calls=int(not result["cache_hit"]),
                            quality_status="not_measured_no_localized_transcript",
                            cer=None,
                            wer=None,
                        )
                    )
            finally:
                resources = with_model.resources()
                with_model.close()
                write_json(output / label / "resources.json", resources)
    assert all(file_hash(path) == value for path, value in hashes.items()), "Originaldateien verändert"
    write_csv(output / "observations.csv", records)
    write_json(
        output / "probe.json",
        dict(
            version=VERSION,
            source=str(source),
            records=records,
            transforms=transforms,
            reference_used=False,
            ocr_identity=engine.identity,
            original_files_unchanged=True,
            source_config_sha256=file_hash(source / "config.yaml"),
            implementation_sha256=file_hash(Path(__file__)),
            selection_rule="No winner without localized reviewed transcripts; output length is not accuracy",
        ),
    )
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(r.get(k, '')))}</td>"
            for k in (
                "engine",
                "variant",
                "page_number",
                "characters",
                "wall_seconds",
                "calls",
                "quality_status",
            )
        )
        + "</tr>"
        for r in records
    )
    (output / "report.html").write_text(
        '<!doctype html><html lang="de"><meta charset="utf-8">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>Handschrift-Voruntersuchung</title><h1>Kontrollierte OCR-Voruntersuchung</h1>"
        "<p>Beobachtungszahlen sind keine Erkennungsqualität. Excel-Kurswerte werden separat als Feldvergleich genutzt; "
        "keine CER/WER ohne unabhängig geprüfte lokalisierte Transkripte. Keine Variante wird automatisch übernommen.</p>"
        "<table><tr><th>Engine</th><th>Variante</th><th>Seite</th><th>Zeichen</th><th>gemessene Zeit (s)</th>"
        "<th>Aufrufe</th><th>Qualitätsstatus</th></tr>"
        + rows
        + '</table><p><a href="probe.json">Konfiguration und Protokoll</a>'
        ' · <a href="observations.csv">Messwerte CSV</a></p></html>',
        encoding="utf-8",
    )
    return output


def compare_docling_probe(source, output, source_report):
    """Only after inference: document-wide field comparison, never region OCR accuracy."""
    from collections import defaultdict

    from participant_bench.excel_reference import ReferencePerson
    from participant_bench.roster_benchmark.config import BenchmarkConfig
    from participant_bench.roster_benchmark.evaluation import map_documents
    from participant_bench.roster_benchmark.matching import Prediction
    from participant_bench.roster_benchmark.metrics import aggregate, course_metrics
    from participant_bench.structured_mapping import extract_structured

    identity = read_json(source_report / "identity.json")
    if Path(identity["source_run"]).resolve() != source.resolve():
        raise ValueError("Kursreferenzvergleich gehört zu einem anderen Quelllauf")
    references = defaultdict(list)
    for row in read_json(source_report / "reference_snapshot.json")["people"]:
        references[row["class_id"]].append(ReferencePerson(**row))
    config = BenchmarkConfig.model_validate(read_json(source_report / "config.json"))
    mapping, _, _ = map_documents(read_json(source / "manifest.json"), set(references))
    results = {}
    for label in ("docling-no-grid", "docling-full-page"):
        predictions, contexts = defaultdict(list), {}
        for page in read_json(source / "effective_pages.json"):
            path = output / label / f"p{page['page_number']:04d}.json"
            if not path.exists():
                continue
            people, _, _, context = extract_structured(read_json(path), contexts.get(page["document_id"]))
            contexts[page["document_id"]] = context
            predictions[mapping[page["document_id"]]].extend(
                Prediction(page["document_id"], page["page_number"], i, person)
                for i, person in enumerate(people)
            )
        results[label] = aggregate(
            [
                course_metrics(
                    course, predictions[course], references[course], config.matching, config.reference
                )[0]
                for course in set(mapping.values()) & set(references)
            ]
        )
    write_json(
        output / "docling_field_quality.json",
        dict(
            reference_scope="document_course_only_not_handwriting_regions",
            reference_sha256=identity["reference_sha256"],
            variants=results,
            baseline=read_json(source_report / "metrics.json")["methods"]["docling"],
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--structures", action="store_true")
    parser.add_argument("--source-report", type=Path)
    args = parser.parse_args()
    result = run(args.source_run, args.output, args.structures)
    if args.source_report and args.structures:
        compare_docling_probe(args.source_run, result, args.source_report)
    print(result)
