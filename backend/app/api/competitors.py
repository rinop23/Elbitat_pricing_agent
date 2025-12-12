from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.models.competitor import CompetitorCreate, Competitor
from app.services.competitor_service import add_competitor, list_competitors, delete_competitor, update_competitor_db

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.post("", response_model=Competitor)
def create_competitor(payload: CompetitorCreate):
    cid = add_competitor(payload.name, str(payload.website) if payload.website else None, payload.active)
    return Competitor(id=cid, **payload.dict())


@router.get("", response_model=List[Competitor])
def get_competitors():
    return list_competitors()


@router.delete("/{cid}")
def remove_competitor(cid: int):
    delete_competitor(cid)
    return {"ok": True}


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    active: Optional[bool] = None
    lighthouse_hotel_id: Optional[str] = None

@router.patch("/{cid}", response_model=Competitor)
def update_competitor(cid: int, payload: CompetitorUpdate):
    updated = update_competitor_db(cid, payload.dict(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return updated
