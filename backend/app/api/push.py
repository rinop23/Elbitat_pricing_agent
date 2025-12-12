from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.clients.simple_booking_client import SimpleBookingClient
from app.core.config import AppConfig
from app.services.pricing_service import get_recommendations

router = APIRouter(prefix="/runs", tags=["runs"])


class PushRequest(BaseModel):
    currency: str = "EUR"


@router.post("/{run_id}/push")
def push_run_rates(run_id: int, payload: PushRequest):
    cfg = AppConfig()
    recs = get_recommendations(run_id)
    if not recs:
        raise HTTPException(status_code=404, detail="No recommendations found for run")

    updates = [
        {
            "date": r["date"],
            "amount": f"{float(r['recommended_rate']):.2f}",
            "currency": payload.currency,
        }
        for r in recs
    ]

    sb = SimpleBookingClient()
    resp = sb.push_rates(cfg.sb_property_id, cfg.sb_rate_plan_id, updates)
    return resp
