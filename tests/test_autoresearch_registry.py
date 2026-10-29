import hashlib
import json
import sqlite3

from src.autoresearch import _prior_screened_template


def test_reuse_same_contract_template_is_blocked(tmp_path):
    root = tmp_path / "quant-lab"
    (root / "registry").mkdir(parents=True)
    source = root / "strategies/candidates/air_template_previous.py"
    source.parent.mkdir(parents=True)
    source.write_text("fixed-reviewed-code")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    db = root / "registry/registry.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE selection_attempts (attempt_id TEXT, contract_id TEXT, stage TEXT, strategy_module TEXT, parameters_json TEXT)")
        con.execute(
            "INSERT INTO selection_attempts VALUES(?,?,?,?,?)",
            ("ATT-001", "CRYPTO_PERPS_1H_V2", "STAGE_1_SIGNAL",
             "strategies/candidates/air_template_previous.py",
             json.dumps({"mode": "shock_reversal"})),
        )
    assert _prior_screened_template(root, "shock_reversal", digest) == "ATT-001"
    assert _prior_screened_template(root, "volume_breakout", digest) is None
    assert _prior_screened_template(root, "shock_reversal", hashlib.sha256(b"different").hexdigest()) is None
