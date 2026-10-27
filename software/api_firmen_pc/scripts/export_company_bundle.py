"""Export selected program sources only; never PDFs, credentials, weights or old private tests."""

import argparse
import zipfile
from pathlib import Path


def bundle_files(software: Path):
    api = software / "api_firmen_pc"
    paths = [software / name for name in ("pyproject.toml", "uv.lock", ".python-version", "README.md")]
    paths += [software / "scripts" / "setup_ocr.py"]
    paths += [software / "configs" / name for name in ("local.yaml", "smoke.yaml")]
    paths += sorted((software / "verarbeitung" / "src" / "participant_bench").rglob("*.py"))
    paths += sorted((software / "vorverarbeitung").glob("*.py"))
    paths += [software / "vorverarbeitung" / "README.md"]
    paths += [api / name for name in ("pyproject.toml", "uv.lock", ".python-version", "README.md", "main.py")]
    paths += sorted(api.glob("*.cmd"))
    paths += sorted((api / "src" / "participant_api").rglob("*.py"))
    paths += sorted((api / "configs").glob("*.yaml"))
    paths += sorted((api / "scripts").glob("*.ps1"))
    paths += sorted((api / "scripts").glob("*.py"))
    paths += sorted((api / "tests").glob("*.py"))
    paths += sorted((api / "docs").glob("*.md"))
    paths += [api / "certificates" / "BMW_Trusted_Certificates_Latest.pem"]
    for path in paths:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(software.resolve()):
            raise ValueError("Exportquelle fehlt oder ist kein regulärer Projektpfad")
        yield path


def build_bundle(output: Path, software: Path | None = None) -> Path:
    software = software or Path(__file__).resolve().parents[2]
    sources = list(bundle_files(software))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            archive.write(source, Path("software") / source.relative_to(software))
        archive.writestr(
            "software/api_firmen_pc/data/pdfs_eingabe/README.md",
            "Die ausgewählten PDFs ausschließlich auf dem Firmen-PC hier ablegen.\n",
        )
        archive.writestr(
            "software/api_firmen_pc/data/cv-test-20261020-093337/README.md",
            "Die ausgewaehlten PDFs fuer start_api_cv_test.cmd auf dem Firmen-PC hier ablegen.\n",
        )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/firmen-pc.zip"))
    args = parser.parse_args()
    print(build_bundle(args.output))
