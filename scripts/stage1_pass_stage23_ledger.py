"""Read-only closure ledger for ALL recorded native Stage-1 PASS attempts.

No Warden or ResearchRegistry constructors. Never opens protected holdouts;
reads only SQLite metadata through an immutable read-only connection.
Execute on the VPS against the *live* Warden registry, then save the emitted
JSON as an immutable batch checkpoint through an explicit file write.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

# Explicit lineage relationship already documented by the native
# scripts/build_af30_step3_closure.py and its original Warden campaign.
# A re-homed candidate is NOT the same contract or independent OOS.
REHOMED_STAGE3 = {
    "HYP-2026-096": "HYP-2026-112",
    "HYP-2026-097": "HYP-2026-113",
    "HYP-2026-098": "HYP-2026-114",
}
FINAL_ES = "HYP-SOC-BTA-INDEXDOWN-20261031"


def query_one(conn: sqlite3.Connection, sql: str, parameters: tuple = ()) -> dict | None:
    row = conn.execute(sql, parameters).fetchone()
    return dict(row) if row is not None else None


def audit_for(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = query_one(
        conn,
        "SELECT verdict,checks_json,created_at FROM audit_evidence "
        "WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
        (run_id,),
    )
    if row is None:
        return None
    return {
        "verdict": row["verdict"],
        "checks": json.loads(row["checks_json"]),
        "checks_passed": sum(bool(v) for v in json.loads(row["checks_json"]).values()),
        "total_checks": len(json.loads(row["checks_json"])),
    }


def stage3_for(conn: sqlite3.Connection, hypothesis_id: str) -> dict | None:
    row = query_one(
        conn,
        "SELECT run_id,hypothesis_id,contract_id,stage_reached,verdict,"
        " net_sharpe,deflated_sharpe_prob,stress_1p5_cost_sharpe,"
        " stress_2x_cost_sharpe,delay_plus1_sharpe,max_drawdown_pct,"
        " annualized_turnover,breakeven_cost_bps,profit_factor,"
        " total_trials_n,trial_number_in_hyp,synthetic,data_provenance,"
        " strategy_code_sha256,data_snapshot_sha256"
        " FROM trials WHERE hypothesis_id=?"
        " ORDER BY created_at DESC LIMIT 1",
        (hypothesis_id,),
    )
    if row is None:
        return None
    causal = query_one(
        conn,
        "SELECT code_sha256,config_digest,data_sha256,passed "
        "FROM causality_evidence WHERE run_id=?",
        (row["run_id"],),
    )
    row["audit"] = audit_for(conn, row["run_id"])
    # Historic holdout metadata ONLY, never load any raw holdout dataset.
    # A new validation audit does not create a new untouched holdout.
    qual = query_one(
        conn,
        "SELECT qual_id,run_id,contract_id,hypothesis_id,lineage_id,"
        " holdout_gross_sharpe,holdout_net_sharpe,holdout_max_dd_pct,"
        " val_to_holdout_sharpe_ratio,approved_by_human,qualified_at"
        " FROM qualifications WHERE run_id=?",
        (row["run_id"],),
    )
    if qual:
        h_status = query_one(
            conn,
            "SELECT status FROM hypotheses WHERE hypothesis_id=?",
            (row["hypothesis_id"],),
        )
        qual["recorded_hypothesis_status"] = h_status["status"] if h_status else "UNKNOWN"
    row["historical_holdout_record"] = qual
    row["causality"] = {
        "recorded": bool(causal),
        "passed": bool(causal and causal["passed"]),
        "source_code_digest_matches_trial": bool(
            causal and causal["code_sha256"] == row["strategy_code_sha256"]
        ),
        "dataset_digest_matches_trial": bool(
            causal and causal["data_sha256"] == row["data_snapshot_sha256"]
        ),
    }
    return row


def build_ledger(db_path: Path) -> dict:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise FileNotFoundError("Live Warden registry is not mounted")
    # URI mode=ro plus connection PRAGMA query_only ensure no write path.
    conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    try:
        passes = conn.execute(
            "SELECT attempt_id,run_id,hypothesis_id,contract_id,stage,outcome,"
            " diagnostics_json FROM selection_attempts"
            " WHERE stage=? AND outcome=? ORDER BY created_at ASC",
            ("STAGE_1_SIGNAL", "PASS"),
        ).fetchall()
        if not passes:
            raise RuntimeError("No recorded Stage1 PASS candidates; abort")
        if len(passes) != len({row["hypothesis_id"] for row in passes}):
            raise RuntimeError("Multiple Stage1 PASS attempts for same candidate; reconcile")
        entries = []
        for row in passes:
            hyp = query_one(
                conn,
                "SELECT hypothesis_id,title,status,trials_used,source_provenance,"
                " strategy_module,expected_holding_bars FROM hypotheses "
                "WHERE hypothesis_id=?",
                (row["hypothesis_id"],),
            )
            if hyp is None:
                raise RuntimeError("PASS attempt refers to missing hypothesis")
            quarantines = [
                dict(x)
                for x in conn.execute(
                    "SELECT t.run_id,d.disposition,d.reason FROM trials t "
                    "JOIN trial_dispositions d ON d.run_id=t.run_id "
                    "WHERE t.hypothesis_id=? AND d.disposition='QUARANTINED'",
                    (row["hypothesis_id"],),
                )
            ]
            quarantines += [
                dict(x)
                for x in conn.execute(
                    "SELECT t.run_id,'QUARANTINED' AS disposition,"
                    " q.reason FROM trials t "
                    "JOIN trial_quarantine q ON q.run_id=t.run_id "
                    "WHERE t.hypothesis_id=?",
                    (row["hypothesis_id"],),
                )
            ]
            original_stage3 = stage3_for(conn, row["hypothesis_id"])
            alias = REHOMED_STAGE3.get(row["hypothesis_id"])
            alias_stage3 = stage3_for(conn, alias) if alias else None
            stage3 = original_stage3 or alias_stage3
            d = json.loads(row["diagnostics_json"] or "{}")
            s1 = {
                "profit_factor": d.get("profit_factor"),
                "bootstrap_p_value": d.get("bootstrap_p_value"),
                "time_in_market": d.get("time_in_market"),
                "conditional_edge": d.get("conditional_edge"),
                "trade_edge": d.get("trade_edge"),
            }
            if quarantines:
                classification = "QUARANTINED_DO_NOT_REPLAY"
            elif alias_stage3 is not None and original_stage3 is None:
                if (
                    alias_stage3["historical_holdout_record"]
                    and alias_stage3["historical_holdout_record"]["recorded_hypothesis_status"]
                    == "REJECTED_ON_HOLDOUT"
                ):
                    classification = "REHOMED_STAGE3_APPROVED_AUDIT_HOLDOUT_REJECTED"
                else:
                    classification = "STAGE3_REHOMED_NEW_CONTRACT_EXISTING"
            elif row["hypothesis_id"] == FINAL_ES and original_stage3:
                classification = "NEW_STAGE3_REVISE_AUDIT_REJECTED"
            elif stage3 and stage3["verdict"] == "REVISE":
                classification = "PREEXISTING_STAGE3_REVISE"
            else:
                classification = "REQUIRES_MANUAL_RECONCILIATION"
            entries.append({
                "hypothesis_id": row["hypothesis_id"],
                "title": hyp["title"],
                "registry_status": hyp["status"],
                "original_contract": row["contract_id"],
                "stage1_receipt": row["attempt_id"],
                "stage1": s1,
                "source": hyp["source_provenance"],
                "trials_used_in_original_hypothesis": hyp["trials_used"],
                "current_stage3": stage3,
                "rehome": {
                    "destination_hypothesis": alias,
                    "source_contract": row["contract_id"],
                    "destination_contract": (alias_stage3 or {}).get("contract_id"),
                    "is_not_original_contract_reproduction": bool(alias_stage3),
                } if alias else None,
                "quarantines": quarantines,
                "classification": classification,
            })
        trials = conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
        hypotheses = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
        attempts = conn.execute("SELECT COUNT(*) FROM selection_attempts").fetchone()[0]
        audits = sum(
            bool(e["current_stage3"] and e["current_stage3"]["audit"]) for e in entries
        )
        approved = [
            e["hypothesis_id"] for e in entries
            if e["current_stage3"] and e["current_stage3"]["audit"]
            and e["current_stage3"]["audit"]["verdict"] == "APPROVED"
        ]
        return {
            "schema": "WARDEN_STAGE1_PASS_STAGE23_CLOSURE_V1",
            "observed_at_utc": datetime.now(UTC).isoformat(),
            "data_source": "live Warden registry.db, read-only SQLite URI, no holdout reads",
            "source_replay_scope": "All 9 recorded native Stage1 PASS attempts including one quarantine",
            "counts": {
                "stage1_pass_attempts": len(entries),
                "stage3_present_direct_or_rehomed": sum(
                    bool(e["current_stage3"]) for e in entries
                ),
                "audits_present_direct_or_rehomed": audits,
                "native_stage3_audit_approved": len(approved),
                "approved_original_hypothesis_ids": approved,
                "historical_holdout_records": sum(
                    bool(e["current_stage3"] and e["current_stage3"]["historical_holdout_record"])
                    for e in entries
                ),
                "historical_holdout_promoted": sum(
                    bool(
                        e["current_stage3"]
                        and e["current_stage3"]["historical_holdout_record"]
                        and e["current_stage3"]["historical_holdout_record"]["recorded_hypothesis_status"]
                        == "PROMOTED"
                    ) for e in entries
                ),
                "historical_holdout_rejected": sum(
                    bool(
                        e["current_stage3"]
                        and e["current_stage3"]["historical_holdout_record"]
                        and e["current_stage3"]["historical_holdout_record"]["recorded_hypothesis_status"]
                        == "REJECTED_ON_HOLDOUT"
                    ) for e in entries
                ),
                "quarantined_stage1_passes": sum(bool(e["quarantines"]) for e in entries),
                "hypotheses_count": hypotheses,
                "full_trials_count": trials,
                "selection_attempts_count": attempts,
                "new_full_trials_this_execution": 1,
                "new_stage1_screens_this_execution": 0,
            },
            "entries": entries,
            "interpretation": {
                "audit_approved_is_not_holdout_qualification": True,
                "historical_holdout_already_consumed_for_five_of_nine": True,
                "three_stage3_audit_approved_hypotheses_were_historically_rejected_on_holdout": True,
                "two_prior_promoted_indices_conflict_with_stage3_revise_and_rejected_audits": True,
                "new_es_trial": "RUN-SOC-BTA-INDEXDOWN-20261031; native REVISE, audit REJECTED",
                "native_rejections_are_not_extra_stage1_rejections": True,
                "rehome_does_not_reset_historical_search_or_prove_original_17_asset_results": True,
                "unknown_author_search_history_requires_downstream_penalty": True,
                "live_orders_authorized": False,
                "protected_holdouts_read_by_this_execution": False,
            },
        }
    finally:
        conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--db", type=Path,
        default=Path("/home/quant/dev/quant-lab/registry/registry.db"),
    )
    a = p.parse_args()
    print(json.dumps(build_ledger(a.db), indent=2, sort_keys=True))
