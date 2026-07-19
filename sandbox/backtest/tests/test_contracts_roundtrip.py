"""Every contracts/examples/*.json must (a) validate against its JSON Schema
and (b) round-trip losslessly through the pydantic mirrors."""

import json
from pathlib import Path

import jsonschema
import pytest

import contracts

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"

CASES = [
    ("strategy_manifest", contracts.StrategyManifest),
    ("backtest_result", contracts.BacktestResult),
    ("paper_result", contracts.PaperResult),
    ("promotion", contracts.Promotion),
    ("events", contracts.Event),
]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.mark.parametrize("name,model", CASES, ids=[c[0] for c in CASES])
def test_example_validates_against_schema(name, model):
    schema = load(CONTRACTS / f"{name}.schema.json")
    instance = load(EXAMPLES / f"{name}.json")
    jsonschema.validate(
        instance, schema, cls=jsonschema.validators.Draft202012Validator
    )


@pytest.mark.parametrize("name,model", CASES, ids=[c[0] for c in CASES])
def test_example_roundtrips_through_model(name, model):
    original = load(EXAMPLES / f"{name}.json")
    parsed = model.model_validate(original)
    dumped = json.loads(parsed.model_dump_json())
    assert dumped == original


def test_live_promotion_requires_complete_two_step_approval():
    promo = contracts.Promotion.model_validate(load(EXAMPLES / "promotion.json"))
    assert promo.to_stage == "live"
    assert promo.human_approval.is_complete()

    incomplete = promo.human_approval.model_copy(update={"confirmation_msg_id": None})
    assert not incomplete.is_complete()
