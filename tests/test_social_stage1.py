"""Social-source Stage 0 to Warden Stage 1 policy tests with isolated fake registry."""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from src.autoresearch import ResearchProposal, autonomous_run
from src.core.models import Evidence, EvidenceKind
from src.harness.openrouter import ModelAttempt, ModelReply


def social_post(source):
    return Evidence(
        source_id=f"social_substack_{source}",
        kind=EvidenceKind.HISTORICAL,
        uri=f"https://reviewed.substack.com/p/{source}",
        published_at="2026-10-10T12:00:00Z",
        available_at="2026-10-29T00:00:00Z",
        archived_at="2026-10-29T00:00:00Z",
        source_version="v1",
        provider="substack_current_public_capture",
        snippet=(
            f"An original backtested Bitcoin buy the dip trading strategy {source}. "
            "Entry occurs when drawdown reaches 12% from the prior seven-day high; "
            "exit after four hours. Reports results after slippage and costs."
        ),
        facts={"platform": "substack", "author": f"trader-{source}"}
    )


def model():
    class Model:
        async def generate(self, *_):
            return ModelReply(
                parsed=ResearchProposal(
                    template_id="dip_7d",
                    mechanism=(
                        "A seven-day shock can create temporary forced-selling pressure in "
                        "crypto that may mean revert over the following few hours."
                    ),
                    counterparty_or_friction=(
                        "Market makers face toxic fills while panicked takers pay spread "
                        "and slippage; rebounds may be insufficient to overcome costs."
                    ),
                    rationale=(
                        "Original source identifies a seven-day drawdown dip buying "
                        "entry and a four-hour exit, which matches one reviewed template."
                    ),
                    cited_source_ids=["social_substack_one"],
                    limitations=["A 2026 source is not independent of the 2025 exploratory validation."],
                ),
                selected_model="test-free-provider",
                attempts=[ModelAttempt("test-free-provider", "ok")]
            )
    return Model()


def prepare(monkeypatch, tmp_path, *, passed, eligible=True, return_code=None):
    import src.autoresearch as app
    checkout = tmp_path / "quant-lab"
    (checkout / "src/warden").mkdir(parents=True)
    (checkout / "src/warden/cli.py").write_text("dummy")
    (checkout / "data/exploratory").mkdir(parents=True)
    (checkout / "data/exploratory/crypto_perps_1h_v2.parquet").write_bytes(b"dummy")
    (checkout / "contracts").mkdir(parents=True)
    (checkout / "contracts/crypto_perps_1h_v2.yaml").write_text("dummy")
    (checkout / "registry").mkdir()
    (checkout / "experiments/active").mkdir(parents=True)
    with sqlite3.connect(checkout / "registry/registry.db") as db:
        db.execute(
            "CREATE TABLE selection_attempts("
            "attempt_id TEXT,contract_id TEXT,stage TEXT,strategy_module TEXT,parameters_json TEXT)"
        )

    calls = []
    def fake_warden(root, *args, **kwargs):
        calls.append(args[0])
        if args[0] == "check-worktree":
            return {"exit_code": 0, "stdout": "verified", "stderr": ""}
        if args[0] == "register-hypothesis":
            return {"exit_code": 0, "stdout": json.dumps({"registered": True}), "stderr": ""}
        if args[0] == "verify":
            return {"exit_code": 0, "stdout": json.dumps({"status": "PASS"}), "stderr": ""}
        if args[0] == "screen":
            return {
                "exit_code": return_code if return_code is not None else (0 if passed else 1),
                "stdout": json.dumps({
                    "passed": passed, "market_eligible": eligible,
                    "data_provenance": "verified_market",
                    "metrics": {"profit_factor": 1.3 if passed else 0.7},
                }), "stderr": ""
            }
        raise AssertionError("Warden must never execute stage 2 / holdout / orders")
    monkeypatch.setattr(app, "_warden_call", fake_warden)
    return checkout, calls


@pytest.mark.asyncio
async def test_social_source_single_original_post_can_register_and_screen(monkeypatch, tmp_path):
    checkout, calls = prepare(monkeypatch, tmp_path, passed=False)
    post = social_post("one")
    result = await autonomous_run(
        checkout, tmp_path / "research",
        model=model(),
        source_bundle=([post], [{"uri": post.uri, "author": "trader-one"}]),
    )
    assert result["disposition"] == "STAGE_1_REJECT"
    assert result["source_mode"] == "PRACTITIONER_CURRENT_CAPTURE_NOT_HISTORICAL_VINTAGE"
    assert result["post_publication_validation"] is True
    assert calls == ["check-worktree", "register-hypothesis", "verify", "screen"]
    assert "STAGE_1" in json.loads((tmp_path / "research" / result["research_id"] / "result.json").read_text())["disposition"]


@pytest.mark.asyncio
async def test_warden_claimed_pass_without_eligible_provenance_is_blocked(monkeypatch, tmp_path):
    checkout, calls = prepare(monkeypatch, tmp_path, passed=True, eligible=False)
    post = social_post("one")
    result = await autonomous_run(
        checkout, tmp_path / "research", model=model(),
        source_bundle=([post], [{"uri": post.uri}]),
    )
    assert result["disposition"] == "BLOCKED_INCONSISTENT_WARDEN_PASS"
    assert calls == ["check-worktree", "register-hypothesis", "verify", "screen"]



def test_source_cadence_blocks_paper_style_timeframe_drift():
    from src.autoresearch import verify_social_rule_support
    source = social_post("momentum")
    source.snippet = (
        "Original Bitcoin cross-sectional momentum system: rank the universe "
        "and rebalances every 21 days, long top bucket and short bottom bucket. "
        "This is a multiweek strategy, not a daily hourly signal."
    )
    proposal = ResearchProposal(
        template_id="cross_section_momentum_7d",
        mechanism="Relative strength persistence in crypto markets could remain after ranking top and bottom coins.",
        counterparty_or_friction="Slippage and perpetual funding can remove gross edge when shorting weak altcoins.",
        rationale="The original post discusses cross-sectional relative momentum and portfolio ranking.",
        cited_source_ids=[source.source_id],
        limitations=["Source rebalance cadence is too slow for the preapproved template."],
    )
    with pytest.raises(ValueError, match="source cadence"):
        verify_social_rule_support(proposal, [source])


def test_source_cadence_matching_four_hour_dip_is_allowed():
    from src.autoresearch import verify_social_rule_support
    source = social_post("dip")
    source.snippet = (
        "Original Bitcoin buy the dip strategy: enter after seven-day drawdown "
        "and hold for 4 hours. This is the tested idea. "
        "Backtested with a recorded cost assumption."
    )
    proposal = ResearchProposal(
        template_id="dip_7d",
        mechanism="Liquidity shocks can overshoot and mean revert after an exceptional short-term selloff.",
        counterparty_or_friction="Spread and fees can offset any small short-lived recovery in volatile crypto markets.",
        rationale="The author's original source specifies a short horizon for the same dip entry and four-hour exit.",
        cited_source_ids=[source.source_id],
        limitations=["The entry threshold differs and must remain a new adaptation."],
    )
    verify_social_rule_support(proposal, [source])



def test_unmapped_code_examples_cannot_enter_warden_stage1():
    from src.autoresearch import verify_social_rule_support
    record = social_post("github")
    record.facts["source_authenticity"] = "CODE_ONLY_UNVALIDATED_NO_EXECUTION"
    record.snippet = (
        "class TrendRiderStrategy: def populate_entry_trend(self, df): "
        "return rsi signals. No validated code mapping or Donchian entry."
    )
    proposal = ResearchProposal(
        template_id="rsi2_trend_pullback",
        mechanism="An oversold indicator could indicate short-term mean reversion.",
        counterparty_or_friction="Taker fees may overwhelm the expected reversion edge.",
        rationale="Code contains a generic RSI indicator but lacks equivalent frozen rules.",
        cited_source_ids=[record.source_id],
        limitations=["The source uses different entry and exit conditions."],
    )
    with pytest.raises(ValueError, match="require explicit rule mapping"):
        verify_social_rule_support(proposal, [record])
