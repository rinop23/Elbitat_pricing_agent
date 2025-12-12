from pydantic import BaseModel


class Recommendation(BaseModel):
    run_id: int
    date: str
    recommended_rate: float
    lowest_competitor: float
