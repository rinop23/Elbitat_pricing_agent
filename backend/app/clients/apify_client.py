"""Minimal server-side Apify REST client.

Uses plain `requests` (already a dependency) to avoid pulling in the Apify SDK.
The APIFY_TOKEN is read from the environment and only ever used here, server-side.
It is never returned to callers and never sent to the browser.

Apify REST docs: https://docs.apify.com/api/v2
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.apify.com/v2"

# Apify run statuses we treat as terminal.
TERMINAL_OK = {"SUCCEEDED"}
TERMINAL_FAIL = {"FAILED", "ABORTED", "TIMED-OUT"}


class ApifyError(RuntimeError):
    """Any problem talking to the Apify API."""


class ApifyClient:
    def __init__(self, token: Optional[str] = None, actor_id: Optional[str] = None):
        self.token = (token or os.getenv("APIFY_TOKEN", "")).strip()
        self.actor_id = (actor_id or os.getenv("APIFY_ACTOR_ID", "voyager/booking-scraper")).strip()
        if not self.token:
            raise ApifyError(
                "APIFY_TOKEN is not set. Add it to your .env / Streamlit secrets."
            )

    # ------------------------------------------------------------------ helpers
    def _actor_path(self) -> str:
        # The REST path uses '~' between username and actor name.
        return self.actor_id.replace("/", "~")

    def _params(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {"token": self.token}
        if extra:
            params.update(extra)
        return params

    # -------------------------------------------------------------------- calls
    def start_run(self, actor_input: Dict[str, Any], timeout_secs: int = 600) -> Dict[str, Any]:
        """Start an actor run asynchronously. Returns the Apify run object's `data`.

        timeout_secs caps the actor run server-side so a stuck run cannot bill forever.
        """
        url = f"{API_BASE}/acts/{self._actor_path()}/runs"
        try:
            resp = requests.post(
                url,
                params=self._params({"timeout": timeout_secs}),
                json=actor_input,
                timeout=60,
            )
        except requests.RequestException as exc:
            raise ApifyError(f"Failed to reach Apify: {exc}") from exc

        if resp.status_code >= 400:
            raise ApifyError(f"Apify start_run HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json().get("data", {})

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Fetch the current state of a run."""
        url = f"{API_BASE}/actor-runs/{run_id}"
        try:
            resp = requests.get(url, params=self._params(), timeout=30)
        except requests.RequestException as exc:
            raise ApifyError(f"Failed to reach Apify: {exc}") from exc
        if resp.status_code >= 400:
            raise ApifyError(f"Apify get_run HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json().get("data", {})

    def get_dataset_items(self, dataset_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Fetch cleaned dataset items as a list of dicts."""
        url = f"{API_BASE}/datasets/{dataset_id}/items"
        try:
            resp = requests.get(
                url,
                params=self._params({"clean": "true", "format": "json", "limit": limit}),
                timeout=120,
            )
        except requests.RequestException as exc:
            raise ApifyError(f"Failed to reach Apify: {exc}") from exc
        if resp.status_code >= 400:
            raise ApifyError(f"Apify dataset HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data if isinstance(data, list) else []

    @staticmethod
    def extract_cost_usd(run_data: Dict[str, Any]) -> Optional[float]:
        """Pull the run's total USD cost from the run object if Apify reported it."""
        for key in ("usageTotalUsd", "costUsd"):
            val = run_data.get(key)
            if isinstance(val, (int, float)):
                return float(val)
        usage = run_data.get("usage") or {}
        val = usage.get("USD_TOTAL") or usage.get("totalUsd")
        return float(val) if isinstance(val, (int, float)) else None
