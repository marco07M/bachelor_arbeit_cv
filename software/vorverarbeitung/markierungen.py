"""Remove editable PDF annotations while preserving redactions and page content."""

from pathlib import Path

import pymupdf


def cleaned_pdf(source: Path) -> tuple[bytes | None, int, int]:
    """Return cleaned bytes, removed annotations and preserved redaction annotations.

    None means no rewrite is needed. The source is only opened for reading.
    PDF content streams, links, form widgets and applied redactions are retained.
    """
    removed, preserved = 0, 0
    with pymupdf.open(source) as document:
        if not document.is_pdf:
            raise ValueError("Datei ist kein lesbares PDF")
        if document.needs_pass:
            raise ValueError("Verschlüsseltes PDF benötigt ein Passwort")
        for page in document:
            # Save references, then reload after each mutation: returned annotation
            # successors can lose their page binding in supported PyMuPDF versions.
            annotations = [(annotation.xref, annotation.type[0]) for annotation in page.annots() or []]
            for xref, kind in annotations:
                if kind == pymupdf.PDF_ANNOT_REDACT:
                    preserved += 1
                else:
                    annotation = page.load_annot(xref)
                    if annotation is None:
                        continue  # A parent deletion can already remove its popup.
                    page.delete_annot(annotation)
                    page = document.reload_page(page)
                    removed += 1
        data = document.tobytes(garbage=4, deflate=True, no_new_id=True) if removed else None
    return data, removed, preserved


def write_exclusive(destination: Path, data: bytes) -> None:
    stream = destination.open("xb")
    try:
        with stream:
            stream.write(data)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
