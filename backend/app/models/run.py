from pydantic import BaseModel
from typing import Optional


class RunCreate(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    dry_run: bool = True
    occupancy: int = 2


class Run(BaseModel):
    id: int
    start_date: str
    end_date: str
    dry_run: bool
    occupancy: int
    status: str
