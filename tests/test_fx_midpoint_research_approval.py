"""Safety regression for human-approved FX OHLCV proxy research proposal.

This intentionally does not activate a protected Warden contract or touch
the live registry. It only checks that the recorded approval is bounded.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "examples/FX_MAJORS_5M_MID_V1_PROPOSAL.yaml"
MANIFEST = ROOT / "examples/FX_MAJORS_5M_MID_V1_DATASET_PROPOSAL.json"
POLICY = ROOT / "examples/FX_MIDPOINT_RESEARCH_POLICY_20261031.md"
PARENT_HASH = "b364e18b03a2c52c4fc2bb8c54834ce992c7dc7ac63b5bef36258fb0f627558b"


def read_documents():
    return (
        yaml.safe_load(PROPOSAL.read_text(encoding="utf-8")),
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        POLICY.read_text(encoding="utf-8"),
    )


def test_midpoint_proposal_is_new_contract_without_price_or_split_substitution():
    draft, manifest, policy = read_documents()
    assert draft["contract_id"] == "FX_MAJORS_5M_MID_V1"
    assert draft["asset_class"] == "fx"
    assert draft["frequency"] == "5m"
    assert draft["exploratory_data_path"] == "data/exploratory/fx_majors_5m.parquet"
    assert draft["data_snapshot_sha256"] == manifest["sha256"] == PARENT_HASH
    assert draft["holdout_data_path"] == "data/holdout/fx_majors_5m.parquet"
    assert draft["val_start"] == "2023-01-01T00:00:00Z"
    assert draft["val_end"] == draft["holdout_start"] == "2025-07-01T00:00:00Z"
    assert draft["label_horizon_bars"] == 48
    assert draft["embargo_bars"] == 12
    assert manifest["contract_id"] == draft["contract_id"]
    assert "PROPOSAL ONLY" in manifest["attestation"]
    assert "not installed" in policy
    assert "independently verified to be the actual quote midpoint" in policy


def test_costs_are_explicit_not_a_zero_cost_midpoint_fill():
    draft, _, policy = read_documents()
    assert draft["execution_mode"] == "NEXT_BAR"
    assert draft["execution_delay_bars"] >= 1
    assert draft["taker_fee_bps"] == pytest.approx(0.2)
    assert draft["slippage_bps"] == pytest.approx(2.8)
    cost_per_side = draft["taker_fee_bps"] + draft["slippage_bps"]
    assert cost_per_side == pytest.approx(3.0)
    assert 2 * cost_per_side == pytest.approx(6.0)
    assert 4 * cost_per_side == pytest.approx(12.0)
    assert "1.3 bps assumed half-spread" in policy
    assert "1.5 bps residual slippage" in policy
    assert "shared Warden writer lock" in policy
    assert "new ID cannot reset DSR/lineage/search penalties" in policy


def test_unapproved_price_source_is_disclosed_not_synthetic_bid_ask():
    _, manifest, policy = read_documents()
    assert "no artificial quote columns" in manifest["attestation"]
    assert "DATA" not in manifest.get("status", "")
    assert "QUOT" not in manifest.get("status", "")
    assert "AUDUSD **97**" in policy
    assert "GBPUSD **19**" in policy
    assert "USDCAD **12**" in policy
    assert "do not" in policy.lower()
    assert "No Warden registration/screen executed" in policy
