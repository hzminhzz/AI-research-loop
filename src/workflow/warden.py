"""Generate native Warden Stage-0 hypothesis YAML; never write to quant-lab itself."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field

from src.core.models import SAFE_ID, StrictModel
from src.workflow.registry import StrategyThesis


class WardenHandoff(StrictModel):
    contract_id: str = Field(pattern=SAFE_ID, max_length=100)
    strategy_family: Literal["rules_ts", "cross_sectional_ml", "carry_rv", "meta_overlay"]
    counterparty_or_friction: str = Field(min_length=20)
    source_provenance: str = Field(min_length=12)
    llm_model_id: str = Field(min_length=1)


def export_warden_hypothesis(
    thesis: StrategyThesis, mapping: WardenHandoff, root: str | Path,
) -> Path:
    """Export an immutable valid HypothesisSpec-shaped YAML. Registration remains Warden-owned."""
    if len(thesis.mechanism.strip()) < 20:
        raise ValueError("Warden requires economic_mechanism >=20 characters")
    if any(not x.strip() for x in thesis.falsification_criteria):
        raise ValueError("Falsification criteria cannot be blank")

    values = {
        "hypothesis_id": thesis.thesis_id,
        "contract_id": mapping.contract_id,
        "title": f"{thesis.market}: {thesis.timeframe}: {thesis.thesis_id}",
        "strategy_family": mapping.strategy_family,
        "economic_mechanism": thesis.mechanism,
        "counterparty_or_friction": mapping.counterparty_or_friction,
        "expected_holding_bars": thesis.expected_holding_bars,
        "falsification_criteria": "; ".join(thesis.falsification_criteria),
        "parent_hypothesis_id": None,
        "source_provenance": (
            f"{mapping.source_provenance}; AI research forecast IDs: "
            f"{', '.join(thesis.parent_forecast_ids) or 'none'}"
        ),
        "llm_model_id": mapping.llm_model_id,
        "strategy_module": "",
    }
    # JSON quoted scalars are legal YAML; no YAML-specific dependency needed.
    text = "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in values.items())
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{thesis.thesis_id}.yaml"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Warden-native Stage-0 hypothesis")
    parser.add_argument("--thesis", required=True, help="StrategyThesis JSON")
    parser.add_argument("--handoff", required=True, help="WardenHandoff JSON")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    thesis = StrategyThesis.model_validate_json(Path(args.thesis).read_text())
    mapping = WardenHandoff.model_validate_json(Path(args.handoff).read_text())
    print(export_warden_hypothesis(thesis, mapping, args.output))


if __name__ == "__main__":
    main()
