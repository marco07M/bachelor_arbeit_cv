"""Small development fixtures. A cursive font simulation is NOT human handwriting."""

import argparse
import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from participant_bench.io import file_hash, write_json, write_jsonl
from participant_bench.schema import GroundTruthPage, VisualParticipant


def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    pdfs = root / "pdfs"
    pdfs.mkdir()
    truth, cases = [], []
    values = [("Max", "Muster", "000007", "ABC-12"), ("Nora", "Fischer", "000008", "")]
    scenarios = [("123456", "native_alias_reordered", False, False),
                 ("123457", "scanned_slight_rotation", True, False),
                 ("123458", "cursive_font_simulation", True, True),
                 ("123459", "organization_outside_table", False, False)]
    for course, scenario, raster, cursive in scenarios:
        outside = scenario == "organization_outside_table"
        data = values[:1] if outside else values
        headers = ["Org.-Einheit", "Last Name", "First Name", "User ID"] if not outside else ["User ID", "First Name", "Last Name"]
        table = [headers, *[([p[3], p[1], p[0], p[2]] if not outside else [p[2],p[0],p[1]]) for p in data]]
        font_status = "native PDF text"
        with pymupdf.open() as document:
            page = document.new_page(width=842, height=595)
            page.insert_text((40, 50), f"Synthetic development fixture {course}", fontsize=14)
            xs = [40, 225, 410, 595, 800] if not outside else [40,290,540,800]
            ys = [100,160,220,280][:len(table)+1]
            if not raster:
                for x in xs:
                    page.draw_line((x,ys[0]),(x,ys[-1]))
                for y in ys:
                    page.draw_line((xs[0],y),(xs[-1],y))
                for r,row in enumerate(table):
                    for c,text in enumerate(row):
                        page.insert_text((xs[c]+8,ys[r]+34),text,fontsize=12)
                if outside:
                    page.insert_text((40,330),"Organisation: ABC-12 (outside the table, no column assignment)",fontsize=12)
            else:
                scale = 2.5
                image = Image.new("RGB", (2105,1488), "white")
                draw = ImageDraw.Draw(image)
                try:
                    font = ImageFont.truetype("arial.ttf", 30)
                except OSError:
                    font = ImageFont.load_default(size=30)
                handwriting = font
                if cursive:
                    try:
                        handwriting = ImageFont.truetype("segoepr.ttf", 30)
                        font_status = "Segoe Print synthetic font; not human handwriting"
                    except OSError:
                        font_status = "No cursive font available; ordinary synthetic printed font"
                else:
                    font_status = "rasterized printed font"
                for x in xs:
                    draw.line((x*scale,ys[0]*scale,x*scale,ys[-1]*scale), fill="black", width=2)
                for y in ys:
                    draw.line((xs[0]*scale,y*scale,xs[-1]*scale,y*scale), fill="black", width=2)
                for r,row in enumerate(table):
                    for c,text in enumerate(row):
                        draw.text(((xs[c]+8)*scale,(ys[r]+17)*scale),text,fill="black",font=handwriting if r else font)
                if scenario == "scanned_slight_rotation":
                    rotated = image.rotate(2, resample=Image.Resampling.BICUBIC, fillcolor="white")
                    image.close()
                    image = rotated
                buffer = io.BytesIO()
                image.save(buffer,format="PNG")
                page.insert_image(page.rect,stream=buffer.getvalue())
                image.close()
            document.save(pdfs / f"{course}.pdf")
        identity = file_hash(pdfs / f"{course}.pdf")
        participants = [VisualParticipant(first_name=first,last_name=last,personnel_number=user,department=org,
                                          signature_present=None).participant() for first,last,user,org in data]
        truth.append(GroundTruthPage(document_id=identity,page_number=1,split="development",
            content_type="other" if cursive else "typed",dependency_group=identity,
            relevant=True,participants=participants).model_dump())
        cases.append(dict(class_id=course,scenario=scenario,source_type=font_status,
                          human_handwriting=False,reference_origin="Specified before inference"))
    write_jsonl(root / "ground_truth.jsonl",truth)
    write_json(root / "cases.json",cases)
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    print(generate(parser.parse_args().output))
