"""Zone normalization and place filtering.

These cover the bug the tool-selection eval caught: the agent emits verbose
location names ("Questrom School of Business") that ZONE_MAP doesn't key on,
which silently returned zero rows instead of erroring.
"""
import pytest

from app.services.places_service import ZONE_MAP, _normalize_zone, search_places


class TestNormalizeZone:
    @pytest.mark.parametrize("raw,expected", [
        ("CDS", "CDS"),
        ("CAS", "CAS"),
        ("West Campus", "West Campus"),
    ])
    def test_exact_zone_names_pass_through(self, raw, expected):
        assert _normalize_zone(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("cds", "CDS"),
        ("cas", "CAS"),
        ("questrom", "Questrom"),
    ])
    def test_matching_is_case_insensitive(self, raw, expected):
        assert _normalize_zone(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("Questrom School of Business", "Questrom"),
        ("Agganis Arena", "Agganis"),
        ("West Campus dorms", "West Campus"),
        ("Engineering building", "ENG"),
    ])
    def test_verbose_llm_output_maps_to_zone_code(self, raw, expected):
        """The regression this function exists for."""
        assert _normalize_zone(raw) == expected

    def test_unknown_location_passes_through_unchanged(self):
        # Callers fall back to filtering on the raw string; normalization must
        # not invent a zone for something genuinely unrecognized.
        assert _normalize_zone("Fenway Park") == "Fenway Park"

    def test_every_zone_map_key_normalizes_to_itself(self):
        # Guards against a future zone whose name is a substring of another,
        # which would silently reroute queries to the wrong zone.
        for zone in ZONE_MAP:
            assert _normalize_zone(zone) == zone


class FakeQuery:
    """Minimal stand-in for a SQLAlchemy query chain."""

    def __init__(self, rows):
        self._rows = rows
        self.filters = []

    def filter(self, *args):
        self.filters.append(args)
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, rows):
        self.query_obj = FakeQuery(rows)

    def query(self, _model):
        return self.query_obj


class FakePlace:
    def __init__(self, name, category="study", features=None, zone="CDS"):
        self.name = name
        self.category = category
        self.building = "Test Hall"
        self.description = "desc"
        self.hours = "9-5"
        self.features = features if features is not None else []
        self.campus_zone = zone


@pytest.mark.asyncio
class TestSearchPlaces:
    async def test_filters_by_requested_features(self):
        rows = [
            FakePlace("Quiet Room", features=["quiet", "outlets"]),
            FakePlace("Loud Cafe", features=["coffee"]),
        ]
        result = await search_places(
            db=FakeDB(rows), location="CDS", place_type="study", features=["quiet"]
        )
        assert [p["name"] for p in result["places"]] == ["Quiet Room"]

    async def test_no_feature_filter_returns_all(self):
        rows = [FakePlace("A"), FakePlace("B")]
        result = await search_places(
            db=FakeDB(rows), location="CDS", place_type="study", features=[]
        )
        assert len(result["places"]) == 2

    async def test_place_with_null_features_is_excluded_when_filtering(self):
        # `features` is nullable in the schema; filtering must not raise on None.
        rows = [FakePlace("No Features", features=None)]
        result = await search_places(
            db=FakeDB(rows), location="CDS", place_type="study", features=["quiet"]
        )
        assert result["places"] == []

    async def test_caps_results_at_five(self):
        rows = [FakePlace(f"P{i}") for i in range(10)]
        result = await search_places(
            db=FakeDB(rows), location="CDS", place_type="any", features=[]
        )
        assert len(result["places"]) == 5

    async def test_normalization_is_actually_applied_to_the_query(self):
        """Guards the wiring, not just the helper.

        `_normalize_zone` being correct is useless if `search_places` doesn't
        call it — which is exactly how the original bug behaved. Assert the
        emitted SQL filters on the resolved zone, never the verbose input.
        """
        db = FakeDB([FakePlace("X")])
        await search_places(
            db=db,
            location="Questrom School of Business",
            place_type="study",
            features=[],
        )
        rendered = " ".join(
            str(clause.compile(compile_kwargs={"literal_binds": True}))
            for args in db.query_obj.filters
            for clause in args
        )
        assert "Questrom School of Business" not in rendered
        # ZONE_MAP["Questrom"] adjacency should drive the filter instead.
        for zone in ZONE_MAP["Questrom"]:
            assert zone in rendered
