from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Dict, List

from app.core.config import AppConfig
from app.clients.lighthouse_client import LighthouseClient
from app.agent.pricing import recommend_rate
from app.services.competitor_service import get_conn


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def create_run(start_date: str, end_date: str, dry_run: bool, occupancy: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (start_date, end_date, dry_run, occupancy, status) VALUES (?, ?, ?, ?, ?)",
        (start_date, end_date, 1 if dry_run else 0, occupancy, "completed")
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def save_recommendations(run_id: int, recs: List[Dict]):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO recommendations (run_id, date, recommended_rate, lowest_competitor) VALUES (?, ?, ?, ?)",
        [(run_id, r["date"], r["recommended_rate"], r["lowest_competitor"]) for r in recs]
    )
    conn.commit()
    conn.close()


def get_recommendations(run_id: int) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, recommended_rate, lowest_competitor FROM recommendations WHERE run_id=? ORDER BY date",
        (run_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"date": r[0], "recommended_rate": r[1], "lowest_competitor": r[2]}
        for r in rows
    ]


def run_pricing(start_date: str, end_date: str, occupancy: int) -> List[Dict]:
    cfg = AppConfig()
    lh = LighthouseClient()

    start = _parse(start_date)
    end = _parse(end_date)

    comp_matrix = lh.get_competitor_rates("", start, end, occupancy=occupancy)

    recs = []
    d = start
    while d <= end:
        comp_prices = list(map(Decimal, comp_matrix.get(d, {}).values()))
        lowest_comp = float(min(comp_prices)) if comp_prices else 0.0
        rec = recommend_rate(d, comp_prices, None, cfg.cfg)

        recs.append({
            "date": d.isoformat(),
            "recommended_rate": float(rec),
            "lowest_competitor": lowest_comp
        })

        d += timedelta(days=1)

    return recs
