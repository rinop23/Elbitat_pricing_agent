from datetime import date
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional, Dict, List


@dataclass
class PricingConfig:
    min_rate: Decimal
    max_rate: Decimal
    weekend_uplift: Decimal
    undercut: Decimal
    lead_buckets: Dict[int, Decimal]
    max_change_pct: Decimal


def _lead_adjustment(days_out: int, buckets: Dict[int, Decimal]) -> Decimal:
    if not buckets:
        return Decimal("0")

    for cutoff in sorted(buckets):
        if days_out <= cutoff:
            return Decimal(buckets[cutoff])

    last_key = sorted(buckets)[-1]
    return Decimal(buckets[last_key])


def _clamp(v: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(v, hi))


def recommend_rate(
    day: date,
    comp_prices: List[Decimal],
    current_rate: Optional[Decimal],
    cfg: PricingConfig,
) -> Decimal:
    if comp_prices:
        base = min(comp_prices) + cfg.undercut
    else:
        base = current_rate if current_rate is not None else cfg.min_rate

    if day.weekday() in (4, 5):
        base += cfg.weekend_uplift

    days_out = (day - date.today()).days
    base += _lead_adjustment(days_out, cfg.lead_buckets)

    bounded = _clamp(base, cfg.min_rate, cfg.max_rate)

    if current_rate is not None:
        cap = (current_rate * cfg.max_change_pct).copy_abs()
        bounded = _clamp(bounded, current_rate - cap, current_rate + cap)

    return bounded.quantize(Decimal("0.01"))
