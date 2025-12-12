import os
import yaml
from decimal import Decimal
from typing import Dict, Optional
from backend.app.agent.pricing import PricingConfig


class AppConfig:
    def __init__(self, path: str = "config/settings.yaml"):
        # allow running from backend/ or root
        if not os.path.exists(path):
            path = os.path.join("..", path)

        with open(path, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f)

        p = y["pricing"]

        self.horizon_days = int(y.get("run", {}).get("horizon_days", 120))
        self.occupancy = int(y.get("run", {}).get("occupancy", 2))
        self.currency = y["hotel"].get("currency", os.getenv("CURRENCY", "EUR"))

        # Simple Booking configuration
        self.sb_property_id = os.getenv("SB_PROPERTY_ID", y["hotel"].get("property_id"))
        self.sb_rate_plan_id = os.getenv("SB_RATE_PLAN_ID", y["hotel"].get("rate_plan_id"))

        self.cfg = PricingConfig(
            min_rate=Decimal(str(p["min_rate"])),
            max_rate=Decimal(str(p["max_rate"])),
            weekend_uplift=Decimal(str(p["weekend_uplift"])),
            undercut=Decimal(str(p["undercut"])),
            lead_buckets={int(k): Decimal(str(v)) for k, v in p.get("lead_buckets", {}).items()},
            max_change_pct=Decimal(str(p["max_change_pct"])),
        )
