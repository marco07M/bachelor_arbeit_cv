"""Presentation order follows source documents and rows, never reference identities."""


def document_order(manifest):
    identifiers = [item["sha256"] for item in manifest.get("inputs", []) if item.get("sha256")]
    identifiers.extend(page["document_id"] for page in manifest.get("pages", []) if page.get("document_id"))
    return {identifier: index for index, identifier in enumerate(dict.fromkeys(identifiers))}


def page_key(page, documents):
    return documents.get(page.document_id, len(documents)), page.page_number


def row_key(row, documents, methods=None):
    methods = methods or {}
    index = row.get("output_index", row.get("prediction_index"))
    has_source = bool(row.get("document_id")) and index not in (None, "")
    return (
        methods.get(row.get("method"), 0),
        not has_source,
        documents.get(row.get("document_id"), len(documents)),
        int(row.get("page_number") or 0),
        int(index or 0),
    )


def ordered_rows(rows, documents, methods=None):
    # Stable ties keep field order and reference-only diagnostics intact.
    return sorted(rows, key=lambda row: row_key(row, documents, methods))
