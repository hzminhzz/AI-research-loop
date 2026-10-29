"""Explicit linear Neyman-style extremization, with a documented factor."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pvariance

from src.core.models import AgentForecastArtifact


@dataclass(frozen=True)
class Consensus:
    probability: float | None
    mean_probability: float | None
    variance: float | None
    participants: int
    abstentions: int
    gamma: float
    base_rate: float


def aggregate(forecasts: list[AgentForecastArtifact], base_rate: float, gamma: float = 1.0,
              minimum_participants: int = 2) -> Consensus:
    if not 0 <= base_rate <= 1 or not 1 <= gamma <= 2:
        raise ValueError("base_rate in [0,1] and gamma in [1,2] required")
    probs = [f.probability_forecast for f in forecasts if
             not f.abstention_flag and f.probability_forecast is not None]
    if len(probs) < minimum_participants:
        return Consensus(None, None, None, len(probs), len(forecasts) - len(probs), gamma, base_rate)
    p_mean = mean(probs)
    # Linear formula from supplied spec; calibrated gamma must be validated OOS.
    p_extreme = min(1., max(0., base_rate + gamma * (p_mean - base_rate)))
    return Consensus(p_extreme, p_mean, pvariance(probs), len(probs),
                     len(forecasts) - len(probs), gamma, base_rate)
