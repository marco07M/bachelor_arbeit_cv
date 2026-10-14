"""Explicit portable extraction of UB Mannheim Windows OCR, with no installer execution."""

import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tools = root / ".tools"
tools.mkdir(exist_ok=True)
if os.name != "nt":
    raise SystemExit("Linux: install system tesseract-ocr + tesseract-ocr-deu + tesseract-ocr-eng + osd.")
version = "5.4.0.20240606"
url = f"https://github.com/UB-Mannheim/tesseract/releases/download/v{version}/tesseract-ocr-w64-setup-{version}.exe"
target = tools / "ocr"
if not (target / "tesseract.exe").is_file():
    data = urllib.request.urlopen(url, timeout=120).read()
    installer = tools / f"tesseract-{version}.exe"
    installer.write_bytes(data)
    seven = tools / "7zip"
    seven.mkdir(exist_ok=True)
    for filename in ("7zr.exe", "7z2604-x64.exe"):
        download = f"https://github.com/ip7z/7zip/releases/download/26.04/{filename}"
        (tools / filename).write_bytes(urllib.request.urlopen(download, timeout=120).read())
    subprocess.run(
        [str(tools / "7zr.exe"), "x", str(tools / "7z2604-x64.exe"), f"-o{seven}", "-y"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [str(seven / "7z.exe"), "x", str(installer), f"-o{target}", "-y"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    if not (target / "tesseract.exe").is_file():
        raise RuntimeError("Installer did not create tesseract.exe")
tessdata = target / "tessdata"
tessdata.mkdir(parents=True, exist_ok=True)
# Pinned language data; setup manifest records hashes and exact URLs.
commit = "87416418657359cb625c412a48b6e1d6d41c29bd"
manifest = {
    "distribution": "UB Mannheim",
    "version": version,
    "installer_url": url,
    "tessdata_fast_revision": commit,
    "files": {},
}
for language in ("deu", "eng", "osd"):
    url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{commit}/{language}.traineddata"
    data = urllib.request.urlopen(url, timeout=120).read()
    (tessdata / f"{language}.traineddata").write_bytes(data)
    manifest["files"][language] = {"url": url, "sha256": hashlib.sha256(data).hexdigest()}
(tools / "ocr/setup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Local OCR installed:", target / "tesseract.exe")
