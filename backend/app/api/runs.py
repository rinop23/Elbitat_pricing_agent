from fastapi import APIRouter
from app.models.run import RunCreate, Run
from app.services.pricing_service import run_pricing, create_run, save_recommendations

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=Run)
def start_run(payload: RunCreate):
    recs = run_pricing(payload.start_date, payload.end_date, payload.occupancy)
    rid = create_run(payload.start_date, payload.end_date, payload.dry_run, payload.occupancy)
    save_recommendations(rid, recs)

    return Run(
        id=rid,
        start_date=payload.start_date,
        end_date=payload.end_date,
        dry_run=payload.dry_run,
        occupancy=payload.occupancy,
        status="completed"
    )
