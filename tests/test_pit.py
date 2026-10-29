from datetime import datetime

import pytest

from src.core.models import Evidence
from src.harness.gates import GateRejected, validate_evidence
from src.tools.pit import PITGateway, PITViolation

CUTOFF = datetime.fromisoformat("2026-01-15T00:00:00+00:00")


def record(**overrides):
    item = dict(source_id="a", kind="historical", uri="https://example.org/a",
                published_at="2026-01-01T00:00:00Z",
                available_at="2026-01-02T00:00:00Z", snippet="historical observation",
                provider="source")
    item.update(overrides)
    return item


def test_revised_data_blocked():
    item = Evidence.model_validate(record(revision_available_at="2026-01-16T00:00:00Z"))
    with pytest.raises(GateRejected):
        validate_evidence(item, CUTOFF)


@pytest.mark.parametrize("field", ["published_at", "available_at"])
def test_future_data_blocked(field):
    with pytest.raises((GateRejected, ValueError)):
        item = Evidence.model_validate(record(**{field: "2026-01-16T00:00:00Z"}))
        validate_evidence(item, CUTOFF)


@pytest.mark.asyncio
async def test_gateway_does_not_trust_provider():
    async def leaky(_):
        return [record(available_at="2026-01-16T00:00:00Z")]
    gateway = PITGateway({"web_search": leaky})
    with pytest.raises(PITViolation):
        await gateway.execute("web_search", {"query": "historical"}, CUTOFF)


@pytest.mark.asyncio
async def test_gateway_forbids_orders_and_cutoff_override():
    async def safe(_):
        return [record()]
    gateway = PITGateway({"web_search": safe})
    with pytest.raises(PITViolation):
        await gateway.execute("submit_order", {}, CUTOFF)
    with pytest.raises(Exception):
        await gateway.execute("web_search",
                              {"query": "historical", "cutoff_date": "2099-01-01T00:00:00Z"},
                              CUTOFF)
