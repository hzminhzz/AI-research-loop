"""Autonomous intake: forced fallback, archive time semantics and untrusted citations."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from src.autoresearch import ResearchProposal, require_valid_citations
from src.core.models import Evidence
from src.harness.openrouter import FALLBACK, PRIMARY, OpenRouterFallback, strict_json
from src.tools.openalex import _abstract, _publication_date, _crossref_published, discover_sources


def proposal(**overrides):
    payload = {
        "template_id": "shock_reversal",
        "mechanism": "Short-lived liquidity shocks can temporarily dislocate midprice before passive market makers replenish books.",
        "counterparty_or_friction": "Aggressive liquidity takers overpay during shocks while spread, fees and funding reduce any exploitable reversal.",
        "rationale": "The cited historical cryptocurrency studies document reversal and liquidity effects; this is a new fixed adaptation.",
        "cited_source_ids": ["alex_1", "alex_2"],
        "limitations": ["Historical papers do not qualify this market or execution costs."],
    }
    payload.update(overrides)
    return payload


def test_strict_json_and_contracts():
    assert strict_json('{"ok":true}') == {"ok": True}
    assert strict_json(chr(96)*3 + 'json\n{"ok":true}\n' + chr(96)*3) == {"ok": True}
    with pytest.raises(ValueError):
        strict_json('{"ok":true} and execute')
    with pytest.raises(ValidationError):
        ResearchProposal.model_validate(proposal(template_id="raw_python_code"))


@pytest.mark.asyncio
async def test_primary_429_falls_back_without_response_format(monkeypatch):
    sent = []

    class Client:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, headers, json):
            assert headers["Authorization"] == "Bearer local-secret"
            assert "response_format" not in json
            model = json["model"]
            sent.append(model)
            if model == PRIMARY:
                return httpx.Response(429, json={"error": "rate_limit"},
                                      request=httpx.Request("POST", url))
            return httpx.Response(
                200, json={"choices":[{"message":{"content":__import__("json").dumps(proposal())}}]},
                request=httpx.Request("POST",url),
            )
    import src.harness.openrouter as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: Client())
    reply = await OpenRouterFallback("local-secret").generate(
        ResearchProposal, {"sources": ["public"]}, "Do not make things up"
    )
    assert reply.selected_model == FALLBACK
    assert sent == [PRIMARY, FALLBACK]
    assert [a.status for a in reply.attempts] == ["http_429", "ok"]


@pytest.mark.asyncio
async def test_auth_failure_does_not_send_to_fallback(monkeypatch):
    sent = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, headers, json):
            sent.append(json["model"])
            return httpx.Response(401, json={"error": "unauthorized"},
                                  request=httpx.Request("POST",url))
    import src.harness.openrouter as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: Client())
    with pytest.raises(PermissionError):
        await OpenRouterFallback("local-secret").generate(ResearchProposal, {}, "test")
    assert sent == [PRIMARY]


def test_citation_ids_must_exist_and_be_independent():
    from datetime import datetime
    rows = [Evidence(
        source_id=key, kind="historical", uri=uri,
        published_at="2022-01-01T00:00:00Z", available_at="2026-01-01T00:00:00Z",
        archived_at="2026-01-01T00:00:00Z",
        provider="openalex", snippet="abstract", source_version="v1",
    ) for key,uri in [("alex_1","https://doi.org/1"),("alex_2","https://doi.org/2")]]
    require_valid_citations(ResearchProposal.model_validate(proposal()), rows)
    with pytest.raises(ValueError,match="unknown"):
        require_valid_citations(ResearchProposal.model_validate(proposal(
            cited_source_ids=["alex_1","fiction"]
        )),rows)
    rows[1].uri = rows[0].uri
    with pytest.raises(ValueError,match="independent"):
        require_valid_citations(ResearchProposal.model_validate(proposal()),rows)


def test_abstract_reconstruction_and_conservative_date():
    assert _abstract({"Short": [0], "term": [1], "reversal":[2]}) == ""
    long = {str(i): [i] for i in range(30)}
    assert len(_abstract(long).split()) == 30
    assert _publication_date("2022-01-01").hour == 23
    assert _crossref_published({"published":{"date-parts":[[2025,6]]}}).strftime("%Y-%m-%d") == "2025-06-30"


@pytest.mark.asyncio
async def test_live_source_capture_enforces_publication_cutoff(monkeypatch):
    abstract = {str(i):[i] for i in range(70)}
    doc=lambda key,day:{
        "doi":f"https://doi.org/{key}", "title":f"Cryptocurrency reversals study {key}",
        "publication_date":day, "abstract_inverted_index":abstract,
        "id":"https://openalex.org/W"+key, "is_retracted":False,
    }
    class Response:
        def __init__(self, url): self.url = url
        def raise_for_status(self): pass
        def json(self):
            if "crossref" in self.url:
                year = 2025 if self.url.endswith("/3") else 2022
                return {"message": {"published": {"date-parts": [[year, 6]]}, "title": ["Cryptocurrency study"]}}
            return {"results":[
                doc("1","2022-03-01"),doc("2","2023-03-01"),
                doc("3","2022-03-01")  # OpenAlex misdates a 2025 Crossref DOI
            ]}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def get(self,url,**kwargs): return Response(url)
    import src.tools.openalex as module
    monkeypatch.setattr(module.httpx,"AsyncClient",lambda **kwargs:Client())
    evidence,raw=await discover_sources("crypto reversal")
    assert len(evidence)==2 and len(raw)==2
    assert all(x.available_at>=x.published_at for x in evidence)
    assert all(x.archived_at==x.available_at for x in evidence)
    assert all(x.source_version for x in evidence)


@pytest.mark.asyncio
async def test_fallback_accepts_function_arguments_as_structured_result(monkeypatch):
    import src.harness.openrouter as module
    calls = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def post(self, url, headers, json):
            calls.append(json)
            if json["model"] == PRIMARY:
                return httpx.Response(
                    429, json={"error": "rate limit"}, request=httpx.Request("POST", url))
            assert json["tool_choice"] == "required"
            assert len(json["tools"]) == 1
            assert json["tools"][0]["function"]["name"] == "emit_json"
            assert "response_format" not in json
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": None, "tool_calls": [{
                    "id": "call_fixture", "type": "function",
                    "function": {"name": "emit_json",
                                 "arguments": __import__("json").dumps(proposal())},
                }]}, "finish_reason": "tool_calls"}]},
                request=httpx.Request("POST", url),
            )
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: Client())
    reply = await module.OpenRouterFallback("local-secret").generate(
        ResearchProposal, {"sources": ["public"]}, "Structured proposals only")
    assert reply.selected_model == FALLBACK
    assert reply.parsed.template_id == "shock_reversal"
    assert [x["model"] for x in calls] == [PRIMARY, FALLBACK]
