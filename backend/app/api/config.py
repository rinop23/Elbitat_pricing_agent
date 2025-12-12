from fastapi import APIRouter

from app.core.config import AppConfig

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config():
    """Expose non-secret configuration used by the UI."""
    cfg = AppConfig()
    return {
        "hotel": {
            "currency": cfg.currency,
            "property_id": cfg.sb_property_id,
            "rate_plan_id": cfg.sb_rate_plan_id,
        },
        "run": {
            "horizon_days": cfg.horizon_days,
            "occupancy": cfg.occupancy,
        },
        "pricing": {
            "min_rate": float(cfg.cfg.min_rate),
            "max_rate": float(cfg.cfg.max_rate),
            "weekend_uplift": float(cfg.cfg.weekend_uplift),
            "undercut": float(cfg.cfg.undercut),
            "lead_buckets": {str(k): float(v) for k, v in (cfg.cfg.lead_buckets or {}).items()},
            "max_change_pct": float(cfg.cfg.max_change_pct),
        },
    }
