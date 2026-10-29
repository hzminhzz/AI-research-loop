"""Continuous, budgeted practitioner-source research campaign until native Stage 1 PASS.

One cycle is safe for cron/systemd. Persistent SQLite tracks every completed cycle;
a lock prevents overlap, and source IDs are immutable per cycle. Stage 1 PASS means
'candidate for further tests', NOT approved or qualified trading alpha.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch import TEMPLATES, _prior_screened_template, autonomous_run
from src.workflow.contract_router import ROUTES
from src.harness.openrouter import OpenRouterFallback, load_openrouter_key
from src.tools.social_sources import DEFAULT_FEEDS, discover_social_sources

DEFAULT_QUANT_LAB = "/home/quant/dev/quant-lab"
DEFAULT_OUTPUT = "runs/social_campaign"
BLOCKED_PREFIXES = ("BLOCKED_",)
SCREENED = {"STAGE_1_PASS", "STAGE_1_REJECT"}
NO_SCREEN = {"ABSTAINED_NO_STAGE_1", "SKIPPED_ALREADY_SCREENED_TEMPLATE",
             "EXHAUSTED_TEMPLATES", "BLOCKED_CITATIONS", "BLOCKED_TEMPLATE_NOT_APPROVED"}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignStore:
    def __init__(self, directory: Path):
        self.root = directory.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "campaign.sqlite3"
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS cycles (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    time_utc TEXT NOT NULL,
                    disposition TEXT NOT NULL,
                    template_id TEXT,
                    model TEXT,
                    sources_json TEXT NOT NULL,
                    report_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_uses (
                    source_id TEXT PRIMARY KEY,
                    first_run_id TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=20)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def locked(self):
        # Same lock for systemd timers and manually invoked cycles.
        fd = os.open(self.root / "campaign.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("another campaign cycle holds the exclusive lock") from exc
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def records(self):
        with self.connect() as db:
            return db.execute(
                "SELECT run_id,time_utc,disposition,template_id,model,sources_json,report_json "
                "FROM cycles ORDER BY seq"
            ).fetchall()

    def used_sources(self) -> set[str]:
        with self.connect() as db:
            return {row[0] for row in db.execute("SELECT source_id FROM source_uses")}

    def screened_count(self) -> int:
        return sum(row[2] in SCREENED for row in self.records())

    def daily_cycles(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(row[1].startswith(today) for row in self.records())

    def stopped_on_pass(self) -> bool:
        return any(row[2] == "STAGE_1_PASS" for row in self.records())

    def record(self, outcome: dict, source_ids: list[str], *, count_sources: bool) -> None:
        run_id = outcome.get("research_id")
        if not run_id:
            raise ValueError("recorded outcome must have research_id")
        disposition = outcome.get("disposition", "BLOCKED_MISSING_DISPOSITION")
        with self.connect() as db:
            db.execute(
                "INSERT INTO cycles(run_id,time_utc,disposition,template_id,model,sources_json,report_json) "
                "VALUES(?,?,?,?,?,?,?)",
                (run_id, _utc(), disposition, outcome.get("template_id"),
                 outcome.get("model"), json.dumps(source_ids),
                 json.dumps(outcome, sort_keys=True, allow_nan=False)),
            )
            if count_sources:
                for source_id in source_ids:
                    db.execute(
                        "INSERT OR IGNORE INTO source_uses(source_id,first_run_id) VALUES(?,?)",
                        (source_id, run_id),
                    )

    def record_source_catalog(self, sources, metadata, health, deferred, gaps) -> None:
        """Persist evidence inventory independent of whether a strategy is selected."""
        path = self.root / "source_catalog.json"
        tmp = self.root / f"source_catalog_{os.getpid()}.tmp"
        sample = [
            {"id": e.source_id, "url": e.uri,
             "provider": doc.get("source_key"), "type": doc.get("authenticity")}
            for e, doc in zip(sources, metadata)
        ]
        tmp.write_text(json.dumps({
            "captured_at": _utc(), "source_health": health,
            "eligible_for_supported_contracts": sample,
            "eligible_for_crypto_contract": sample,  # legacy catalog reader alias
            "deferred_for_other_contracts": deferred, "source_gaps": gaps,
        }, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)

    def checkpoint(self, state: dict) -> None:
        target = self.root / "status.json"
        temp = self.root / f"status_{os.getpid()}.tmp"
        temp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
        os.replace(temp, target)

    def status(self) -> dict:
        rows = self.records()
        saved = self.root / "status.json"
        details = json.loads(saved.read_text()) if saved.exists() else {}
        catalog = self.root / "source_catalog.json"
        sources = json.loads(catalog.read_text()) if catalog.exists() else {}
        return {
            **details,
            "source_gaps": sources.get("source_gaps", details.get("source_gaps", [])),
            "source_health": sources.get("source_health", []),
            "eligible_post_count": len(sources.get("eligible_for_supported_contracts",
                                                   sources.get("eligible_for_crypto_contract", []))),
            "deferred_post_count": len(sources.get("deferred_for_other_contracts", [])),
            "total_cycles": len(rows),
            "total_screened": sum(r[2] in SCREENED for r in rows),
            "total_passed_stage1": sum(r[2] == "STAGE_1_PASS" for r in rows),
            "total_rule_fidelity_blockers": sum(r[2] in {
                "BLOCKED_RULE_FIDELITY", "BLOCKED_SOURCE_UNIVERSE_MISMATCH",
                "BLOCKED_CONTRACT_OR_EXECUTION"} for r in rows),
            "last_results": [
                {"run_id": x[0], "date": x[1], "disposition": x[2],
                 "template": x[3], "model": x[4]}
                for x in rows[-5:]
            ],
        }


async def inspect_sources_only(
    store: CampaignStore, *, feeds: tuple[str, ...] = DEFAULT_FEEDS,
    social_discovery=discover_social_sources,
) -> dict:
    """Capture the source catalog without models, Warden, or trial consumption."""
    with store.locked():
        discovered = await social_discovery(feeds=feeds, limit=50)
        sources, metadata, gaps = discovered
        health = getattr(discovered, "health", [])
        deferred = getattr(discovered, "deferred", [])
        store.record_source_catalog(sources, metadata, health, deferred, gaps)
        return {
            "status": "SOURCE_DISCOVERY_ONLY",
            "sources": health, "gaps": gaps,
            "eligible_crypto": len(sources), "deferred_other_markets": len(deferred),
            "warden_trials_consumed": 0,
        }


async def run_cycle(
    store: CampaignStore, checkout: Path, *, model: OpenRouterFallback | None = None,
    env_file: str = ".env", max_screened: int = 20, max_daily_cycles: int = 6,
    feeds: tuple[str, ...] = DEFAULT_FEEDS,
    social_discovery=discover_social_sources,
    research_runner=autonomous_run,
) -> dict:
    if not 1 <= max_screened <= 100 or not 1 <= max_daily_cycles <= 24:
        raise ValueError("invalid scientific/cost budgets")
    with store.locked():
        if (store.root / "STOP").exists():
            state = {"status": "MANUALLY_STOPPED", "updated_at": _utc()}
        elif store.stopped_on_pass():
            state = {"status": "STAGE_1_PASS_STOPPED", "updated_at": _utc()}
        elif store.screened_count() >= max_screened:
            state = {"status": "SCIENTIFIC_BUDGET_EXHAUSTED", "updated_at": _utc()}
        elif store.daily_cycles() >= max_daily_cycles:
            state = {"status": "PAUSED_DAILY_QUOTA", "updated_at": _utc()}
        else:
            # Selection history is contract-specific: an old eight-major
            # attempt cannot preclude a distinctly registered broad-universe
            # contract, nor does rewriting source code replenish a trial.
            source_code = Path(__file__).parent / "workflow/strategy_templates.py"
            import hashlib
            digest = hashlib.sha256(source_code.read_bytes()).hexdigest()
            excluded = {
                mode for mode in TEMPLATES
                if _prior_screened_template(
                    checkout, mode, digest, ROUTES[mode].contract_id
                ) is not None
            }
            if not (set(TEMPLATES) - excluded):
                state = {
                    "status": "WAITING_NEW_APPROVED_TEMPLATES",
                    "updated_at": _utc(), "screened_modes": sorted(excluded),
                }
            else:
                discovered = await social_discovery(feeds=feeds, limit=50)
                sources, metadata, source_gaps = discovered
                source_health = getattr(discovered, "health", [])
                deferred = getattr(discovered, "deferred", [])
                store.record_source_catalog(
                    sources, metadata, source_health, deferred, source_gaps,
                )
                used = store.used_sources()
                # Read snippets from distinct, previously unconsumed original posts.
                fresh = [(src, doc) for src, doc in zip(sources, metadata)
                         if src.source_id not in used]
                # A single independently authored, fully specified strategy is
                # sufficient. Do not block on two unrelated posts.
                cohort = fresh[:5]
                if len(cohort) < 1:
                    state = {
                        "status": "WAITING_NEW_VERIFIED_POSTS",
                        "updated_at": _utc(), "source_gaps": source_gaps,
                        "unseen_eligible_posts": len(cohort),
                    }
                else:
                    client = model or OpenRouterFallback(load_openrouter_key(env_file))
                    social_bundle = ([src for src, _ in cohort], [doc for _, doc in cohort])
                    outcome = await research_runner(
                        checkout, store.root / "research", query="Original practitioner strategy rules from ranked blogs, Substack and GitHub",
                        model=client, source_bundle=social_bundle, excluded_templates=excluded,
                    )
                    disposition = outcome.get("disposition", "")
                    # Retry transport/auth failures, but do not re-query the
                    # same permanently unmappable social rule forever.
                    used_count = disposition not in {"BLOCKED_MODEL", "BLOCKED_STAGE_1_OUTPUT"}
                    cited = outcome.get("source_ids") or []
                    observed = [src.source_id for src, _ in cohort]
                    consumed = [sid for sid in cited if sid in observed]
                    store.record(outcome, consumed or observed[:1],
                                 count_sources=used_count)
                    state = {
                        "status": (
                            "STAGE_1_PASS_STOPPED" if disposition == "STAGE_1_PASS"
                            else "RESEARCH_CYCLE_COMPLETE"
                        ),
                        "updated_at": _utc(), "last_run_id": outcome.get("research_id"),
                        "last_disposition": disposition, "last_template": outcome.get("template_id"),
                        "last_model": outcome.get("model"),
                        "last_contract_id": outcome.get("contract_id"),
                        "last_scientific_status": outcome.get("scientific_status"),
                        "last_block_reason": outcome.get("reason"),
                        "source_gaps": source_gaps,
                        "next_step": (
                            "Manual scientific review; Stage 1 PASS is NOT production qualification"
                            if disposition == "STAGE_1_PASS" else
                            "Search next original rule; do not repeat a blocked or screened source"
                        ),
                    }
        store.checkpoint(state)
        return store.status()


async def run_continuously(store: CampaignStore, checkout: Path, *,
                           interval_seconds: int, **kwargs):
    if interval_seconds < 300:
        raise ValueError("minimum polling interval is five minutes")
    while True:
        status = await run_cycle(store, checkout, **kwargs)
        print(json.dumps(status, indent=2), flush=True)
        if status["status"] in {
            "STAGE_1_PASS_STOPPED", "SCIENTIFIC_BUDGET_EXHAUSTED",
            "MANUALLY_STOPPED",
        }:
            return
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded continuous social-source Warden research")
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument("--once", action="store_true", help="Execute one campaign cycle")
    commands.add_argument("--loop", action="store_true", help="Poll until Stage 1 pass or budget exhaustion")
    commands.add_argument("--status", action="store_true")
    commands.add_argument("--sources-only", action="store_true",
                          help="Refresh source health without LLM or Warden")
    commands.add_argument("--stop", action="store_true")
    commands.add_argument("--resume", action="store_true")
    parser.add_argument("--quant-lab", default=DEFAULT_QUANT_LAB)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--max-screened", type=int, default=20)
    parser.add_argument("--max-daily-cycles", type=int, default=6)
    parser.add_argument("--interval-seconds", type=int, default=1800)
    args = parser.parse_args()
    store = CampaignStore(Path(args.output))
    if args.status:
        print(json.dumps(store.status(), indent=2))
        return
    if args.sources_only:
        print(json.dumps(asyncio.run(inspect_sources_only(store)), indent=2))
        return
    if args.stop:
        (store.root / "STOP").touch(exist_ok=True)
        print(json.dumps({"status": "MANUALLY_STOPPED"}))
        return
    if args.resume:
        (store.root / "STOP").unlink(missing_ok=True)
        print(json.dumps({"status": "RESUMED"}))
        return
    options = {
        "env_file": args.env_file,
        "max_screened": args.max_screened,
        "max_daily_cycles": args.max_daily_cycles,
    }
    checkout = Path(args.quant_lab)
    if args.loop:
        asyncio.run(run_continuously(
            store, checkout, interval_seconds=args.interval_seconds, **options
        ))
    else:
        print(json.dumps(asyncio.run(run_cycle(store, checkout, **options)), indent=2))


if __name__ == "__main__":
    main()
