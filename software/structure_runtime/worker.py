"""Persistent JSON-lines worker. All native stdout and diagnostics stay in the local stderr log."""

import base64
import importlib.metadata
import io
import json
import os
import sys
import time

from offline import disable_network
from PIL import Image


def main():
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    disable_network()
    backend, loaded, calls = None, 0.0, 0
    for line in sys.stdin:
        try:
            request = json.loads(line)
            command = request["command"]
            if command == "close":
                break
            if command == "init":
                started = time.perf_counter()
                if request["method"] == "paddle_structure":
                    from paddle_backend import PaddleBackend

                    backend = PaddleBackend(request["settings"])
                elif request["method"] == "docling":
                    from docling_backend import DoclingBackend

                    backend = DoclingBackend(request["settings"])
                else:
                    raise ValueError("Unknown structure method")
                loaded = time.perf_counter() - started
                result = dict(backend.resources(), load_seconds=loaded,
                              packages={d.metadata["Name"]: d.version for d in importlib.metadata.distributions()})
            elif command == "recognize" and backend is not None:
                started = time.perf_counter()
                with Image.open(io.BytesIO(base64.b64decode(request["png"]))) as image:
                    pdf_bytes = base64.b64decode(request["pdf"]) if request.get("pdf") else None
                    result = backend.recognize(image, pdf_bytes)
                calls += 1
                result["elapsed_seconds"] = time.perf_counter() - started
                result["resources"] = dict(backend.resources(), load_seconds=loaded, calls=calls)
            else:
                raise ValueError("Initialize worker before recognizing pages")
            response = {"ok": True, "result": result}
        except Exception as exc:
            # Document content and full traceback remain in the user's local diagnostic log.
            import traceback

            traceback.print_exc(file=sys.stderr)
            response = {"ok": False, "error": f"Local structure worker failed ({type(exc).__name__}); see runtime log"}
        protocol.write(json.dumps(response, ensure_ascii=True) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
