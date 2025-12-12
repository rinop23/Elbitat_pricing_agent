from fastapi import APIRouter
from typing import List
from app.models.recommendation import Recommendation
from app.services.pricing_service import get_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/{run_id}", response_model=List[Recommendation])
def recommendations_for_run(run_id: int):
    recs = get_recommendations(run_id)
    return [Recommendation(run_id=run_id, **r) for r in recs]
