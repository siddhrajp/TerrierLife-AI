from fastapi import APIRouter, Depends, Query

from app.db.connection import get_db
from app.services.places_service import search_places

router = APIRouter()


@router.get("/places")
async def get_places(
    location: str = Query(default="GSU"),
    place_type: str = Query(default="any"),
    features: list[str] = Query(default=[]),
    max_walk_minutes: int = Query(default=10),
    db=Depends(get_db),
):
    return await search_places(
        db=db,
        location=location,
        place_type=place_type,
        features=features,
        max_walk_minutes=max_walk_minutes,
    )
