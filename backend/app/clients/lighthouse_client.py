from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict
import os


class LighthouseClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("LIGHTHOUSE_API_KEY", "")
        self.base_url = base_url or os.getenv("LIGHTHOUSE_BASE_URL", "")

    def get_competitor_rates(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
        occupancy: int = 2
    ) -> Dict[date, Dict[str, Decimal]]:
        days = (end_date - start_date).days + 1
        data = {}
        for i in range(days):
            d = start_date + timedelta(days=i)
            base = Decimal(100 + (i % 7) * 5)
            data[d] = {
                "COMP_A": base,
                "COMP_B": base + Decimal("7"),
                "COMP_C": base - Decimal("3"),
            }
        return data
