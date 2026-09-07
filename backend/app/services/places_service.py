from sqlalchemy.orm import Session
from app.models.db_models import Place

ZONE_MAP = {
    "CDS": ["CDS", "Questrom", "GSU"],
    "CAS": ["CAS", "Mugar", "GSU"],
    "GSU": ["GSU", "CAS", "CDS"],
    "Questrom": ["Questrom", "CDS", "GSU"],
    "COM": ["COM", "CAS", "GSU"],
    "ENG": ["ENG", "CDS", "Agganis"],
    "Agganis": ["Agganis", "ENG", "West Campus"],
    "West Campus": ["West Campus", "Agganis", "ENG"],
    "StuVi": ["StuVi", "West Campus", "CDS"],
}


def _normalize_zone(location: str) -> str:
    """Map a possibly-verbose location (e.g. 'Questrom School of Business',
    as the LLM sometimes extracts it) back to the short zone code ZONE_MAP
    expects, via case-insensitive substring match."""
    loc_lower = location.lower()
    for zone in ZONE_MAP:
        zone_lower = zone.lower()
        if zone_lower == loc_lower or zone_lower in loc_lower or loc_lower in zone_lower:
            return zone
    return location


async def search_places(
    db: Session,
    location: str,
    place_type: str,
    features: list | None = None,
    max_walk_minutes: int = 10,
) -> dict:
    query = db.query(Place)

    if place_type != "any":
        query = query.filter(Place.category == place_type)

    if location:
        zone = _normalize_zone(location)
        nearby_zones = ZONE_MAP.get(zone, [zone])
        query = query.filter(Place.campus_zone.in_(nearby_zones))

    places = query.limit(10).all()

    if features:
        places = [
            p
            for p in places
            if p.features and any(f in p.features for f in features)
        ]

    return {
        "places": [
            {
                "name": p.name,
                "category": p.category,
                "building": p.building,
                "description": p.description,
                "hours": p.hours,
                "features": p.features,
                "campus_zone": p.campus_zone,
            }
            for p in places[:5]
        ]
    }
