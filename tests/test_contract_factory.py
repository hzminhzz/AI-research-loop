"""Bounded contract derivation must preserve original Warden scientific boundaries."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.workflow.contract_factory import (
    ContractBlocked, ContractRequest, assert_existing_manifest_unchanged,
    propose_contract,
)


def _fixture(tmp_path):
    root = tmp_path / "quant-lab"
    (root / "contracts/datasets").mkdir(parents=True)
    (root / "data/exploratory").mkdir(parents=True)
    (root / "registry").mkdir(parents=True)
    pq.write_table(
        pa.table({
            "timestamp": pa.array([
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
            ], type=pa.timestamp("us", tz="UTC")),
            "asset": ["BTCUSDT", "BTCUSDT"],
            "open": [100., 100.], "high": [105., 105.],
            "low": [95., 95.], "close": [101., 101.],
            "volume": [1000., 1000.], "funding_rate": [0.0001, 0.0001],
        }),
        root / "data/exploratory/pinned.parquet",
    )
    sha = hashlib.sha256((root / "data/exploratory/pinned.parquet").read_bytes()).hexdigest()
    cid = "CRYPTO_PERPS_TOP100_1H_V1"
    contract = {
        "contract_id": cid, "asset_class": "crypto_perps",
        "frequency": "1h", "bars_per_year": 8760,
        "exploratory_data_path": "data/exploratory/pinned.parquet",
        "holdout_data_path": "data/holdout/sealed.parquet",
        "train_start": "2023-01-01T00:00:00Z",
        "val_start": "2024-07-01T00:00:00Z",
        "val_end": "2025-07-01T00:00:00Z",
        "holdout_start": "2025-07-01T00:00:00Z",
        "holdout_end": "2026-10-24T00:00:00Z",
        "n_folds": 4,
        "label_horizon_bars": 4, "embargo_bars": 4,
        "execution_delay_bars": 1,
        "execution_mode": "NEXT_BAR",
        "taker_fee_bps": 4.0, "slippage_bps": 2.0,
        "funding_bps_per_8h": 1.0,
        "min_expected_move_to_cost_ratio": 2.5,
        "data_snapshot_sha256": sha, "data_provenance": "verified_market",
    }
    cp = root / f"contracts/{cid.lower()}.yaml"
    cp.write_text(yaml.safe_dump(contract), encoding="utf-8")
    mp = root / f"contracts/datasets/{cid}.json"
    mp.write_text(json.dumps({
        "contract_id": cid,
        "path": "data/exploratory/pinned.parquet",
        "sha256": sha, "provenance": "verified_market",
        "source": "pinned verified Binance public data", "pipeline": "fixture",
    }))
    (root / "AGENTS.md").write_text("# Already protected policy", encoding="utf-8")
    files = [cp, mp, root / "AGENTS.md"]
    lines = [f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(root)}"
             for f in files]
    (root / ".warden_manifest.sha256").write_text("\n".join(lines) + "\n")
    return root


def _req(**changes):
    opts = {
        "parent_contract_id": "CRYPTO_PERPS_TOP100_1H_V1",
        "research_family": "xsmom_21d",
        "label_horizon_bars": 504,
        "expected_holding_bars": 504,
        "source_url": "https://stoicresearch.substack.com/p/14-cross-sectional-momentum",
        "source_published_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "source_captured_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
        "source_revision_sha256": "a" * 64,
        "reason_for_new_contract": (
            "Original twenty-one day cross-sectional rotation cannot safely use "
            "the existing four-hour label and two-hour embargo."
        ),
        "min_taker_fee_bps": 4.5,
        "min_slippage_bps": 2.0,
        "requires_funding": True,
    }
    opts.update(changes)
    return ContractRequest(**opts)


def test_factory_uses_original_data_original_splits_cost_floors_and_reviewable_lineage(tmp_path):
    root = _fixture(tmp_path)
    before = sorted((root / "contracts").glob("*.yaml"))
    proposal = propose_contract(root, _req())
    assert proposal.contract_id.startswith("AUTO_CRYPTO_PERPS_TOP100_1H_V1_H504_E504")
    assert proposal.requires_manifest_approval is True
    assert proposal.source_after_validation is True
    assert proposal.parent_selection_attempts == 0
    result = proposal.as_dict()
    item = result["contract"]
    assert item["label_horizon_bars"] == item["embargo_bars"] == 504
    assert item["val_start"] == "2024-07-01T00:00:00Z"
    assert item["holdout_start"] == "2025-07-01T00:00:00Z"
    assert item["holdout_data_path"] == "data/holdout/sealed.parquet"
    assert not (root / "data/holdout").exists()
    assert item["taker_fee_bps"] == 4.5
    assert item["slippage_bps"] == 2.0
    assert result["manifest"]["sha256"] == item["data_snapshot_sha256"]
    assert result["provenance"]["holdout_accessed"] is False
    assert len(list((root / "contracts").glob("*.yaml"))) == len(before)


@pytest.mark.parametrize("params,needle", [
    ({"label_horizon_bars": 1440, "expected_holding_bars": 1440}, "fold too short"),
    ({"label_horizon_bars": 24, "expected_holding_bars": 1000}, "shorter than intended"),
    ({"requires_quote_data": True}, "bid/ask"),
    ({"requires_open_interest": True}, "open interest"),
])
def test_unsafe_requests_fail_closed(tmp_path, params, needle):
    root = _fixture(tmp_path)
    with pytest.raises(ContractBlocked, match=needle):
        propose_contract(root, _req(**params))


def test_prior_manifest_mutation_refused_even_if_git_clean(tmp_path):
    root = _fixture(tmp_path)
    (root / "AGENTS.md").write_text("# Unapproved Warden governance modification")
    with pytest.raises(ContractBlocked, match="Previously approved file changed"):
        propose_contract(root, _req())


def test_dataset_digest_or_provenance_cannot_be_laundered(tmp_path):
    root = _fixture(tmp_path)
    with (root / "data/exploratory/pinned.parquet").open("ab") as fp:
        fp.write(b"\n")
    with pytest.raises(ContractBlocked, match="Dataset hash drift"):
        propose_contract(root, _req())
    root = _fixture(tmp_path / "fresh")
    parent = root / "contracts/datasets/CRYPTO_PERPS_TOP100_1H_V1.json"
    item = json.loads(parent.read_text())
    item["provenance"] = "unknown"
    parent.write_text(json.dumps(item))
    with pytest.raises(ContractBlocked, match="Previously approved file changed"):
        propose_contract(root, _req())


def test_contract_proposal_cannot_rewrite_an_existing_contract(tmp_path):
    root = _fixture(tmp_path)
    proposal = propose_contract(root, _req())
    target = root / "contracts" / (proposal.contract_id.lower() + ".yaml")
    target.write_text(proposal.contract_yaml)
    with pytest.raises(ContractBlocked, match="already exists"):
        propose_contract(root, _req())


def test_existing_semantics_are_reused_not_rebranded(tmp_path):
    root = _fixture(tmp_path)
    with pytest.raises(ContractBlocked, match="already provides"):
        propose_contract(root, _req(label_horizon_bars=4,
                                    expected_holding_bars=4,
                                    min_taker_fee_bps=4.,
                                    min_slippage_bps=2.))



def test_delegated_activation_adds_only_two_pinned_research_files(tmp_path):
    from src.workflow.contract_factory import activate_contract
    root = _fixture(tmp_path)
    original = (root / ".warden_manifest.sha256").read_text()
    with pytest.raises(ContractBlocked, match="principal"):
        activate_contract(root, _req(), delegated_approval=None)
    assert (root / ".warden_manifest.sha256").read_text() == original
    out = activate_contract(
        root, _req(),
        delegated_approval="principal-approved-2026-10-30-research-contracts",
    )
    assert out["status"] == "ACTIVATED_DELEGATED_RESEARCH_CONTRACT"
    assert out["independent_signature"] == "none"
    assert out["holdout_accessed"] is False
    assert (root / ".warden_manifest.sha256").read_text().startswith(original)
    assert len(assert_existing_manifest_unchanged(root)) == 5
    assert not (root / "data/holdout").exists()
    meta = json.loads((root / ".warden_manifest.sha256.meta.json").read_text())
    assert meta["mode"] == "bounded_principal_delegation_unsigned"
    assert set(meta["added_paths"]) == {
        f"contracts/{out['contract_id'].lower()}.yaml",
        f"contracts/datasets/{out['contract_id']}.json",
    }
    with pytest.raises(ContractBlocked, match="already exists"):
        propose_contract(root, _req())


def test_independent_warden_signatures_are_never_overwritten(tmp_path):
    from src.workflow.contract_factory import activate_contract
    root = _fixture(tmp_path)
    (root / ".warden_manifest.sha256.sig").write_text("signature owned by human")
    with pytest.raises(ContractBlocked, match="Independent Warden signature"):
        activate_contract(
            root, _req(),
            delegated_approval="principal-approved-2026-10-30-research-contracts",
        )
    assert sorted((root / "contracts").glob("auto_*.yaml")) == []



def test_auto_research_reuses_derived_contract_on_same_snapshot(tmp_path):
    from src.workflow.contract_factory import activate_contract, find_compatible_contract
    root = _fixture(tmp_path)
    assert find_compatible_contract(root, _req()) is None
    out = activate_contract(
        root, _req(),
        delegated_approval="principal-approved-2026-10-30-research-contracts",
    )
    assert find_compatible_contract(root, _req()) == out["contract_id"]
    assert find_compatible_contract(root, _req(
        label_horizon_bars=4, expected_holding_bars=4,
        min_taker_fee_bps=4.0, min_slippage_bps=2.0,
    )) == "CRYPTO_PERPS_TOP100_1H_V1"
