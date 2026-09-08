"""Agent-adjacent pure logic: response typing, token accounting, event ranking."""
import pytest

from app.services.events_service import search_events
from app.services.openai_service import _sum_token_usage, detect_response_type


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
