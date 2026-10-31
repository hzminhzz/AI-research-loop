"""Immutable, no-registry-access checks for Stage1 PASS -> Stage2/3 closure.

Only reads source-only JSON artifacts. These tests must never open a live
Warden registry, instantiate ExperimentRunner, or touch a sealed holdout.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "examples/STAGE1_PASS_STAGE23_CLOSURE_20261031.json"
STAGE2 = ROOT / "examples/STAGE2_ES_INDEXDOWN_20261031.json"


def test_all_nine_native_passes_have_an_accounted_disposition():
    evidence = json.loads(CLOSURE.read_text(encoding="utf-8"))
    counts = evidence["counts"]
    rows = evidence["entries"]
    assert counts["stage1_pass_attempts"] == len(rows) == 9
    assert len({x["hypothesis_id"] for x in rows}) == 9
    assert all(x["stage1_receipt"].startswith("ATT-") for x in rows)
    assert all(x["current_stage3"] is not None for x in rows)
    assert counts["stage3_present_direct_or_rehomed"] == 9
    assert counts["quarantined_stage1_passes"] == 1
    assert counts["new_stage1_screens_this_execution"] == 0
    assert counts["new_full_trials_this_execution"] == 1
    assert (counts["hypotheses_count"], counts["full_trials_count"], counts["selection_attempts_count"]) == (
        148, 72, 183
    )


def test_approved_related_af30_three_are_not_misrepresented_as_original_contract():
    evidence = json.loads(CLOSURE.read_text(encoding="utf-8"))
    rows = {x["hypothesis_id"]: x for x in evidence["entries"]}
    for original, related in {
        "HYP-2026-096": "RUN-HYP112-003",
        "HYP-2026-097": "RUN-HYP113-003",
        "HYP-2026-098": "RUN-HYP114-003",
    }.items():
        x = rows[original]
        assert x["classification"] == "REHOMED_STAGE3_APPROVED_AUDIT_HOLDOUT_REJECTED"
        assert x["original_contract"] == "MULTI_ASSET_1D_V1"
        assert x["rehome"]["destination_contract"] == "INDICES_1D_V1"
        assert x["rehome"]["is_not_original_contract_reproduction"] is True
        stage3 = x["current_stage3"]
        assert stage3["run_id"] == related
        assert stage3["verdict"] == "CANDIDATE_FOR_QUALIFICATION"
        assert stage3["audit"]["verdict"] == "APPROVED"
        assert stage3["audit"]["checks_passed"] == stage3["audit"]["total_checks"] == 6
        assert stage3["causality"]["passed"] is True
        assert stage3["causality"]["source_code_digest_matches_trial"] is True
        assert stage3["causality"]["dataset_digest_matches_trial"] is True
        assert stage3["historical_holdout_record"]["recorded_hypothesis_status"] == "REJECTED_ON_HOLDOUT"
        assert stage3["historical_holdout_record"]["holdout_net_sharpe"] < 0.8
    assert evidence["counts"]["native_stage3_audit_approved"] == 3
    assert evidence["counts"]["historical_holdout_records"] == 5
    assert evidence["counts"]["historical_holdout_promoted"] == 2
    assert evidence["counts"]["historical_holdout_rejected"] == 3
    assert evidence["interpretation"]["audit_approved_is_not_holdout_qualification"] is True
    assert evidence["interpretation"]["protected_holdouts_read_by_this_execution"] is False
    for old in ("HYP-2026-065", "HYP-2026-069"):
        stage3 = {row["hypothesis_id"]: row for row in evidence["entries"]}[old]["current_stage3"]
        assert stage3["verdict"] == "REVISE"
        assert stage3["audit"]["verdict"] == "REJECTED"
        assert stage3["historical_holdout_record"]["recorded_hypothesis_status"] == "PROMOTED"


def test_es_new_native_trial_is_failure_without_changing_stage1():
    evidence = json.loads(CLOSURE.read_text(encoding="utf-8"))
    rows = {x["hypothesis_id"]: x for x in evidence["entries"]}
    es = rows["HYP-SOC-BTA-INDEXDOWN-20261031"]
    assert es["stage1_receipt"] == "ATT-4f8505fedde82ba2-001"
    assert es["classification"] == "NEW_STAGE3_REVISE_AUDIT_REJECTED"
    stage3 = es["current_stage3"]
    assert stage3["run_id"] == "RUN-SOC-BTA-INDEXDOWN-20261031"
    assert stage3["stage_reached"] == "STAGE_3_STRESS"
    assert stage3["verdict"] == "REVISE"
    assert stage3["deflated_sharpe_prob"] < 0.90
    assert stage3["delay_plus1_sharpe"] < 0
    assert stage3["audit"]["verdict"] == "REJECTED"
    assert stage3["audit"]["checks_passed"] == 4
    assert stage3["audit"]["checks"]["2_outlier_sensitivity"] is False
    assert stage3["audit"]["checks"]["5_cost_and_latency_survival"] is False
    assert stage3["causality"]["passed"] is True
    assert stage3["trial_number_in_hyp"] == 1
    residual = rows["HYP-2026-128"]
    assert residual["classification"] == "QUARANTINED_DO_NOT_REPLAY"
    assert residual["quarantines"]
    assert residual["current_stage3"]["audit"]["verdict"] != "APPROVED"


def test_stage2_cost_latency_and_session_attribution_is_scientifically_labelled():
    d = json.loads(STAGE2.read_text(encoding="utf-8"))
    identity = d["identity"]
    assert identity["hypothesis_id"] == "HYP-SOC-BTA-INDEXDOWN-20261031"
    assert identity["data_provenance"] == "verified_market"
    assert identity["never_read_holdout"] is True
    assert identity["registry_connection_created"] is False
    assert d["native_read_only_execution"]["1x"]["metrics"]["net_sharpe"] > 1.03
    assert 0.9 < d["native_read_only_execution"]["2x"]["metrics"]["net_sharpe"] < 1
    assert d["native_read_only_execution"]["lag_plus1"]["metrics"]["net_sharpe"] < 0
    assert d["outlier_sensitivity"]["net_sharpe_after_zeroing_best5pct"] < -1
    assert d["cash_clock_reconciliation"]["native_daily_bars_with_sunday"] == 129
    assert d["cash_clock_reconciliation"]["cash_session_unsupported_return_bars"]["bars"] == 260
    assert d["limitation"]["session_eligibility_for_source_replication"].startswith("BLOCKED")
    assert "synthetic?" not in d["limitation"]["original_cash_day_reproduction"]
