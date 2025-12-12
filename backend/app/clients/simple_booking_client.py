import os
from typing import Optional, Dict


class SimpleBookingClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("SB_API_KEY", "")
        self.base_url = base_url or os.getenv("SB_BASE_URL", "")

    def get_current_rates(self, property_id: str, rate_plan_id: str, start_date, end_date) -> Dict:
        """
        MOCK: return empty dict (no current prices)
        """
        return {}

    def push_rates(self, property_id: str, rate_plan_id: str, updates):
        """
        MOCK: simulate sending rates.
        """
        return {
            "status": "mocked",
            "num_updates": len(updates)
        }
