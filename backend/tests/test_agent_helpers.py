"""Agent-adjacent logic and wiring: response typing, token accounting,
event ranking, and citation plumbing."""
import pytest

from app.services.events_service import search_events
from app.services.openai_service import (
    _dedupe_sources,
    _sum_token_usage,
    detect_response_type,
)


class TestDetectResponseType:
    @pytest.mark.parametrize("message,expected", [
        ("What events are on this week?", "events"),
        ("Any hackathon coming up?", "events"),
        ("How do I apply for OPT?", "resource"),
        ("Where can I get tutoring?", "resource"),
        ("I have 20 minutes before class", "time_assistant"),
        ("Quiet study spot with outlets", "places"),
    ])
    def test_classifies_message(self, message, expected):
        assert detect_response_type(message) == expected

    def test_is_case_insensitive(self):
        assert detect_response_type("ANY EVENTS THIS WEEK?") == "events"

    def test_defaults_to_places(self):
        assert detect_response_type("hello") == "places"


class FakeMsg:
    def __init__(self, inp=0, out=0):
        self.usage_metadata = {"input_tokens": inp, "output_tokens": out}


class TestSumTokenUsage:
    def test_sums_across_every_step_of_the_loop(self):
        usage = _sum_token_usage([FakeMsg(100, 20), FakeMsg(150, 30)])
        assert usage == {"input_tokens": 250, "output_tokens": 50}

    def test_ignores_messages_without_usage_metadata(self):
        # Tool and human messages carry no usage; they must not break accounting.
        plain = type("Plain", (), {})()
        assert _sum_token_usage([FakeMsg(10, 5), plain]) == {
            "input_tokens": 10, "output_tokens": 5
        }

    def test_empty_message_list(self):
        assert _sum_token_usage([]) == {"input_tokens": 0, "output_tokens": 0}


class FakeEvent:
    def __init__(self, title, tags):
        self.title = title
        self.description = "d"
        self.location = "GSU"
        self.event_date = "2026-09-10"
        self.category = "c"
        self.tags = tags
        self.source_url = "https://bu.edu/e"


class FakeEventQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return self._rows


class FakeEventDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return FakeEventQuery(self._rows)


@pytest.mark.asyncio
class TestSearchEvents:
    async def test_ranks_by_interest_overlap(self):
        rows = [
            FakeEvent("One tag", ["ai"]),
            FakeEvent("Two tags", ["ai", "startup"]),
        ]
        result = await search_events(
            db=FakeEventDB(rows), interests=["ai", "startup"]
        )
        assert result["events"][0]["title"] == "Two tags"

    async def test_matching_is_case_insensitive(self):
        rows = [FakeEvent("Match", ["Artificial-Intelligence"])]
        result = await search_events(db=FakeEventDB(rows), interests=["artificial"])
        assert len(result["events"]) == 1

    async def test_falls_back_to_all_events_when_nothing_matches(self):
        """Better to show upcoming events than an empty list."""
        rows = [FakeEvent("Unrelated", ["knitting"])]
        result = await search_events(db=FakeEventDB(rows), interests=["quantum"])
        assert len(result["events"]) == 1

    async def test_handles_events_with_no_tags(self):
        rows = [FakeEvent("Untagged", None)]
        result = await search_events(db=FakeEventDB(rows), interests=["ai"])
        assert len(result["events"]) == 1


class TestDedupeSources:
    """The agent can call search_bu_resource more than once in a single ReAct
    loop, so the same page arrives twice and must not be cited twice."""

    def test_collapses_repeats_by_url(self):
        out = _dedupe_sources([
            {"title": "OPT", "url": "https://bu.edu/isso/opt"},
            {"title": "OPT", "url": "https://bu.edu/isso/opt"},
            {"title": "CPT", "url": "https://bu.edu/isso/cpt"},
        ])
        assert [s["url"] for s in out] == [
            "https://bu.edu/isso/opt",
            "https://bu.edu/isso/cpt",
        ]

    def test_preserves_retrieval_order(self):
        # Ranking is meaningful — the first retrieved source is the strongest.
        out = _dedupe_sources([
            {"url": "b"}, {"url": "a"}, {"url": "b"}, {"url": "c"},
        ])
        assert [s["url"] for s in out] == ["b", "a", "c"]

    def test_empty(self):
        assert _dedupe_sources([]) == []


class FakeFinal:
    """Stands in for the agent's closing AIMessage."""
    content = "You can file for OPT through the ISSO."
    usage_metadata = {"input_tokens": 10, "output_tokens": 5}
    tool_calls = None


class TestSourcesReachTheResponse:
    """Isolated-helper tests do not prove the helper is called. _dedupe_sources
    can be perfect while handle_query still drops citations on the floor —
    which is the bug this cycle set out to fix. Assert the wiring itself."""

    @pytest.mark.asyncio
    async def test_retrieved_sources_are_returned_to_the_caller(self, monkeypatch):
        from app.services import openai_service as svc

        async def fake_search(db, query):
            return {
                "context": "OPT is administered by the ISSO.",
                "chunks": ["OPT is administered by the ISSO."],
                "sources": [{"title": "OPT", "url": "https://bu.edu/isso/opt", "category": "intl"}],
            }

        def fake_create_react_agent(llm, tools):
            by_name = {t.name: t for t in tools}

            class FakeAgent:
                async def ainvoke(self, state, config=None):
                    # Simulate the ReAct loop actually reaching for the RAG tool.
                    await by_name["search_bu_resource"].ainvoke({"query": "OPT"})
                    return {"messages": [FakeFinal()]}

            return FakeAgent()

        monkeypatch.setattr(svc, "search_bu_resources", fake_search)
        monkeypatch.setattr(svc, "create_react_agent", fake_create_react_agent)
        monkeypatch.setattr(svc, "load_history", lambda db, sid: [])
        monkeypatch.setattr(svc, "save_turn", lambda db, sid, u, a: None)

        result = await svc.handle_query(
            message="How do I apply for OPT?",
            location=None, time_available=None, interests=None,
            db=None, session_id=None,
        )

        assert result["sources"] == [
            {"title": "OPT", "url": "https://bu.edu/isso/opt", "category": "intl"}
        ], "citations built by the retriever must survive the trip to the response"

    @pytest.mark.asyncio
    async def test_queries_that_never_retrieve_return_no_sources(self, monkeypatch):
        from app.services import openai_service as svc

        def fake_create_react_agent(llm, tools):
            class FakeAgent:
                async def ainvoke(self, state, config=None):
                    return {"messages": [FakeFinal()]}
            return FakeAgent()

        monkeypatch.setattr(svc, "create_react_agent", fake_create_react_agent)
        monkeypatch.setattr(svc, "load_history", lambda db, sid: [])
        monkeypatch.setattr(svc, "save_turn", lambda db, sid, u, a: None)

        result = await svc.handle_query(
            message="hello", location=None, time_available=None,
            interests=None, db=None, session_id=None,
        )
        assert result["sources"] == []
