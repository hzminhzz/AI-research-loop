"""Batch CLI. Defaults to offline fixtures. Real research requires configured sources."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from src.core.models import ResearchQuestion
from src.harness.model import DeterministicDemoModel, OpenAICompatibleModel
from src.multi_agent.runner import MultiAgentRunner
from src.tools.pit import PITGateway
from src.tools.providers import fixture_provider


async def run_batch(args: argparse.Namespace) -> None:
    questions = [ResearchQuestion.model_validate(x) for x in
                 json.loads(Path(args.questions).read_text(encoding="utf-8"))]
    if not questions:
        raise ValueError("at least one question required")
    provider = fixture_provider(args.evidence)
    gateway = PITGateway({"web_search": provider, "market_lookup": provider})

    def model_factory(index: int, role: str):
        if args.demo:
            return DeterministicDemoModel()
        return OpenAICompatibleModel(model=args.model, base_url=args.base_url,
                                     temperature=min(0.8, 0.2 + index * 0.1))

    results = []
    for q in questions:
        runner = MultiAgentRunner(model_factory, gateway, args.output, workers=args.workers,
                                  gamma=args.gamma, max_steps=args.steps)
        result = await runner.run(q)
        results.append({"research_id": q.research_id,
                        "forecasts": [x.model_dump(mode="json") for x in result.forecasts],
                        "consensus": result.consensus.__dict__,
                        "qualification": "RESEARCH_ONLY_NOT_BACKTEST_VALIDATED"})
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    (root / "batch.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only point-in-time research ensemble")
    parser.add_argument("--questions", default="examples/questions.json")
    parser.add_argument("--evidence", default="examples/evidence.json")
    parser.add_argument("--output", default="runs")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--demo", action="store_true", help="Synthetic fixtures only")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    args = parser.parse_args()
    if not args.demo:
        raise SystemExit("Live LLM mode needs a real PIT provider. Configure one before use; do not treat fixtures as live data.")
    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
