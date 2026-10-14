from pathlib import Path

from PIL import Image, ImageDraw

from participant_bench.config import load_config
from participant_bench.models import LocalModel
from participant_bench.rules import signature
from participant_bench.schema import Box


def test_signature_ink_not_automatically_positive():
    config = load_config(Path("configs/smoke.yaml"))
    blank = Image.new("RGB", (400, 200), "white")
    box = Box(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
    assert signature(blank, box, {}, config)[0] is False
    ImageDraw.Draw(blank).line([(40, 90), (75, 60), (110, 130), (170, 75)], fill="black", width=3)
    assert signature(blank, box, {}, config)[0] is None
    assert signature(blank, None, {}, config)[0] is None
    straight = Image.new("RGB", (400, 200), "white")
    ImageDraw.Draw(straight).line([(50, 100), (300, 100)], fill="black", width=3)
    assert signature(straight, box, {}, config)[0] is None


def test_generation_failure_not_reported_as_schema_error():
    # Unit test of failure accounting only; this is never a model smoke-test substitute.
    model = object.__new__(LocalModel)
    model.method = "vlm"
    model.spec = load_config(Path("configs/local.yaml")).models["vlm"]
    model.calls = 0

    def failed_generation(*args, **kwargs):
        raise RuntimeError("simulated OOM for status unit test")

    model.generate = failed_generation
    rows, responses, status, _ = model.extract(Image.new("RGB", (256, 256)))
    assert status == "failed" and not rows
    assert responses[0]["parse_status"] == "not_attempted"
    assert responses[0]["error_stage"] == "generation"
    assert model.calls == 1
