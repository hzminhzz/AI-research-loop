"""Batch research CLI; demo fixtures are never silently used in archive/LLM mode."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from src.core.models import ResearchQuestion
from src.harness.model import DeterministicDemoModel, OpenAICompatibleModel
from src.multi_agent.runner import MultiAgentRunner
from src.multi_agent.supervisor import SupervisorAgent
from src.tools.archive import ArchivedCatalog
from src.tools.pit import PITGateway
from src.tools.providers import fixture_provider


async def run_batch(args: argparse.Namespace) -> None:
    questions = [
        ResearchQuestion.model_validate(x)
        for x in json.loads(Path(args.questions).read_text(encoding="utf-8"))
    ]
    if not questions:
        raise ValueError("at least one research question required")

    if args.demo:
        provider = fixture_provider(args.evidence)
        digest = hashlib.sha256(Path(args.evidence).read_bytes()).hexdigest()
        gateway = PITGateway({"web_search": provider, "market_lookup": provider},
                             source_digest=digest)
    else:
        if not args.archive or not args.archive_sha256:
            raise ValueError("live research needs --archive and --archive-sha256")
        catalog = ArchivedCatalog(args.archive, args.archive_sha256)
        gateway = PITGateway(
            {"web_search": catalog.query, "market_lookup": catalog.query},
            require_archive=True, source_digest=catalog.sha256,
        )

    def model_factory(index: int, role: str):
        if args.demo:
            return DeterministicDemoModel()
        return OpenAICompatibleModel(
            model=args.model, base_url=args.base_url,
            temperature=min(0.8, 0.2 + index * 0.1),
        )

    results = []
    for q in questions:
        supervisor = None
        if not args.demo:
            supervisor = SupervisorAgent(
                OpenAICompatibleModel(model=args.model, base_url=args.base_url, temperature=0.1),
                gateway, args.output,
            )
        runner = MultiAgentRunner(
            model_factory, gateway, args.output, workers=args.workers,
            gamma=args.gamma, max_steps=args.steps, supervisor=supervisor,
        )
        result = await runner.run(q)
        results.append({
            "research_id": q.research_id,
            "forecasts": [x.model_dump(mode="json") for x in result.forecasts],
            "consensus": result.consensus.__dict__,
            "supervisor": result.supervisor.__dict__,
            "qualification": "RESEARCH_ONLY_NOT_BACKTEST_VALIDATED",
            "source_mode": "SYNTHETIC_DEMO" if args.demo else "PINNED_ARCHIVE",
        })
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    (root / "batch.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only point-in-time research ensemble"
    )
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--demo", action="store_true", help="Synthetic fixture mode")
    sources.add_argument("--archive", help="Pinned, versioned historical capture JSON")
    parser.add_argument("--archive-sha256", help="Expected SHA-256 of archive file")
    parser.add_argument("--questions", default="examples/questions.json")
    parser.add_argument("--evidence", default="examples/evidence.json")
    parser.add_argument("--output", default="runs/v3")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    args = parser.parse_args()
    if not args.demo and args.questions == "examples/questions.json":
        parser.error("archive mode requires an explicit real research question file")
    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
