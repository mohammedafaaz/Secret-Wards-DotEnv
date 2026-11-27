import json
from pathlib import Path

from models.v2.model_runtime import CandidateModels
from sheild.engine import Engine


FIXTURE = Path(__file__).parent / "fixtures" / "model_address_label_regression.json"


def test_model_preserves_address_label_after_relative_name():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = Engine("synthetic-regression-secret", CandidateModels()).clean_text(fixture["input"])
    assert actual == fixture["expected_safe_output"]
