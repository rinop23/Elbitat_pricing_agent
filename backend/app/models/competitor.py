from pydantic import BaseModel, HttpUrl
from typing import Optional


class CompetitorCreate(BaseModel):
    name: str
    website: Optional[HttpUrl] = None
    active: bool = True


class Competitor(CompetitorCreate):
    id: int
