"""Rate-shopping service: competitor pricing intelligence via Apify + Supabase.

Responsibilities
----------------
* CRUD for competitor hotels (and the Elbitat "self" listing).
* Build the Apify (Booking.com) actor input for a given stay.
* Start / poll / sync Apify runs.
* Normalise raw dataset items into hotel_price_observations (adapter clearly marked).
* Compute Elbitat-vs-competitor insights and a suggested action per date.
* Cost-control safeguards (horizon cap, competitor cap, duplicate-run suppression).

Everything here is server-side. The Apify token and DB connection string never reach
the browser. Booking.com is the default source; switch actors via APIFY_ACTOR_ID and
adapt `normalise_item` if the new actor's output shape differs.
"""
from __future__ import annotations

import math
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from psycopg2.extras import Json, RealDictCursor

from backend.app.core.db import get_conn
from backend.app.clients.apify_client import ApifyClient, TERMINAL_OK, TERMINAL_FAIL, ApifyError


# ----------------------------------------------------------------------------
# Config / safeguards
# ----------------------------------------------------------------------------
def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


MAX_HORIZON_DAYS = _int_env("RATESHOP_MAX_HORIZON_DAYS", 120)
MAX_COMPETITORS = _int_env("RATESHOP_MAX_COMPETITORS", 15)
MAX_DATES_PER_MANUAL_RUN = _int_env("RATESHOP_MAX_DATES_PER_MANUAL_RUN", 14)
DEDUP_WINDOW_HOURS = _int_env("RATESHOP_DEDUP_WINDOW_HOURS", 12)
DEFAULT_CURRENCY = os.getenv("PRICING_DEFAULT_CURRENCY", os.getenv("CURRENCY", "EUR"))

# Recommendation thresholds.
ABOVE_MARKET_PCT = 0.15          # >15% over median = "expensive"
HIGH_AVAIL_RATIO = 0.5           # >=50% of competitors bookable = healthy supply
SOLD_OUT_RATIO = 0.25            # <=25% bookable = tight market
FALLING_PRICE_PCT = 0.05         # median dropped >5% vs prior scrape = softening


# ----------------------------------------------------------------------------
# Competitor hotels CRUD
# ----------------------------------------------------------------------------
def list_competitor_hotels(active_only: bool = False) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM rateshop.competitor_hotels"
    if active_only:
        sql += " WHERE active = true"
    sql += " ORDER BY is_self DESC, name ASC"
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def add_competitor_hotel(
    name: str,
    booking_url: Optional[str] = None,
    location: Optional[str] = None,
    source: str = "booking",
    active: bool = True,
    is_self: bool = False,
    notes: Optional[str] = None,
) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO rateshop.competitor_hotels
                (name, booking_url, location, source, active, is_self, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (name, booking_url, location, source, active, is_self, notes),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return int(new_id)
    finally:
        conn.close()


def update_competitor_hotel(hotel_id: int, fields: Dict[str, Any]) -> None:
    allowed = {"name", "booking_url", "location", "source", "active", "is_self", "notes"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = %s" for k in fields)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE rateshop.competitor_hotels SET {sets} WHERE id = %s",
            (*fields.values(), hotel_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_competitor_hotel(hotel_id: int) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM rateshop.competitor_hotels WHERE id = %s", (hotel_id,))
        conn.commit()
    finally:
        conn.close()


def seed_competitor_hotels(rows: List[Dict[str, Any]]) -> int:
    """Insert seed rows, skipping any whose name already exists. Returns count inserted."""
    existing = {h["name"].strip().lower() for h in list_competitor_hotels()}
    inserted = 0
    for r in rows:
        if not r.get("name") or r["name"].strip().lower() in existing:
            continue
        add_competitor_hotel(
            name=r["name"],
            booking_url=r.get("booking_url"),
            location=r.get("location"),
            source=r.get("source", "booking"),
            active=r.get("active", True),
            is_self=r.get("is_self", False),
            notes=r.get("notes"),
        )
        inserted += 1
    return inserted


# ----------------------------------------------------------------------------
# Apify input builder (Booking.com)
# ----------------------------------------------------------------------------
def _normalize_url(raw: Optional[str]) -> Optional[str]:
    """Return a syntactically valid http(s) URL, or None if it cannot be salvaged.

    Adds a missing scheme and trims whitespace. Rejects anything without a proper host
    (e.g. a hotel name accidentally typed into the URL field) so we can fall back to a
    name search instead of sending Apify an invalid startUrl.
    """
    s = (raw or "").strip()
    if not s:
        return None
    if not s.lower().startswith(("http://", "https://")):
        s = "https://" + s
    parsed = urlparse(s)
    if not parsed.netloc or " " in parsed.netloc or "." not in parsed.netloc:
        return None
    return s


def _booking_url_with_dates(
    url: str, check_in: date, check_out: date, adults: int, children: int, currency: str
) -> str:
    """Append stay params to a Booking.com hotel URL so the actor scrapes those dates."""
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    q.update(
        {
            "checkin": [check_in.isoformat()],
            "checkout": [check_out.isoformat()],
            "group_adults": [str(adults)],
            "group_children": [str(children)],
            "no_rooms": ["1"],
            "selected_currency": [currency],
        }
    )
    new_query = urlencode({k: v[0] for k, v in q.items()})
    return urlunparse(parsed._replace(query=new_query))


def build_booking_input(
    hotels: List[Dict[str, Any]],
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
    currency: str,
) -> Dict[str, Any]:
    """Build actor input for ONE stay across all given hotels.

    Hotels with a booking_url are passed as startUrls (precise). Hotels without one are
    passed as free-text searches. Adjust the keys here if you switch to another actor.
    """
    start_urls = []
    searches = []
    for h in hotels:
        norm_url = _normalize_url(h.get("booking_url"))
        if norm_url:
            start_urls.append(
                {"url": _booking_url_with_dates(norm_url, check_in, check_out, adults, children, currency)}
            )
        else:
            # No URL, or the URL field held something that isn't a real URL -> search by name.
            loc = h.get("location") or "Isola d'Elba"
            searches.append(f"{h['name']} {loc}")

    actor_input: Dict[str, Any] = {
        "checkIn": check_in.isoformat(),
        "checkOut": check_out.isoformat(),
        "adults": adults,
        "children": children,
        "rooms": 1,
        "currency": currency,
        "language": "en-gb",
        # buffer so search-based lookups can return a couple of candidates per hotel
        "maxItems": max(len(hotels) * 3, 10),
        "propertyType": "none",
        "sortBy": "distance_from_search",
    }
    if start_urls:
        actor_input["startUrls"] = start_urls
    if searches:
        # The booking actor accepts a single search string; join is a pragmatic fallback.
        actor_input["search"] = searches[0] if len(searches) == 1 else ", ".join(searches)
    return actor_input


# ----------------------------------------------------------------------------
# Normalisation adapter  >>> ADAPT THESE MAPPINGS to your actor's output <<<
# ----------------------------------------------------------------------------
# Expected Booking.com (voyager/booking-scraper) item fields (best-effort):
#   name | hotelName, url, address, price | priceText, currency, available | rooms, ...
# Each item is mapped to one observation. The stay context (check_in/out, guests) comes
# from the run's search_params because the actor does not always echo it back.

def _first(item: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in item and item[k] not in (None, "", []):
            return item[k]
    return None


_CURRENCY_SYMBOLS = {"€": "EUR", "£": "GBP", "$": "USD", "CHF": "CHF"}


def _normalize_currency(raw: Any, default: str) -> str:
    """Map a currency symbol/code to an ISO code, falling back to the default."""
    s = str(raw or "").strip()
    if not s:
        return default
    if s in _CURRENCY_SYMBOLS:
        return _CURRENCY_SYMBOLS[s]
    return s[:8] if s.isalpha() else default


def _to_float_price(raw: Any) -> Optional[float]:
    """Parse a price that may be a number, '€1.234,50', '1,234.50', or 'EUR 120'."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None
    s = str(raw)
    digits = "".join(c for c in s if c.isdigit() or c in ".,")
    if not digits:
        return None
    # Heuristic: if both separators present, the last one is the decimal separator.
    if "," in digits and "." in digits:
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits:
        # treat comma as decimal if it looks like cents (",dd" at the end)
        digits = digits.replace(",", ".") if len(digits.split(",")[-1]) == 2 else digits.replace(",", "")
    try:
        val = float(digits)
        return val if val > 0 else None
    except ValueError:
        return None


def normalise_item(
    item: Dict[str, Any],
    *,
    search_params: Dict[str, Any],
    default_currency: str,
) -> Optional[Dict[str, Any]]:
    """Convert one raw dataset item into an observation dict (or None to skip)."""
    name = _first(item, ["name", "hotelName", "title"])
    if not name:
        return None

    check_in = search_params["check_in"]
    check_out = search_params["check_out"]
    nights = search_params["nights"]

    # voyager/booking-scraper puts room-level data in a `rooms` array; the lead price /
    # availability / room type are best read from there, falling back to top-level fields.
    rooms = item.get("rooms") if isinstance(item.get("rooms"), list) else []
    room_prices = [p for p in (_to_float_price(r.get("price")) for r in rooms) if p]

    price = _to_float_price(_first(item, ["price", "priceText", "minPrice", "totalPrice"]))
    if price is None and room_prices:
        price = min(room_prices)
    currency = _normalize_currency(_first(item, ["currency", "currencyCode"]), default_currency)

    # Availability: explicit flag if present, else any bookable room, else infer from price.
    avail_raw = _first(item, ["available", "isAvailable", "hasAvailability"])
    if isinstance(avail_raw, bool):
        available = avail_raw
    elif rooms:
        available = any(r.get("available") for r in rooms) or price is not None
    else:
        available = price is not None

    room_type = _first(item, ["roomType", "roomName", "unitType"])
    if not room_type and rooms:
        room_type = rooms[0].get("roomType") or rooms[0].get("bedType")

    breakfast = _first(item, ["breakfastIncluded", "breakfast", "mealPlan"])
    if isinstance(breakfast, str):
        breakfast = "breakfast" in breakfast.lower()

    return {
        "hotel_name": str(name).strip(),
        "source": str(search_params.get("source", "booking")),
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "guests_adults": search_params["adults"],
        "guests_children": search_params["children"],
        "room_type": room_type,
        "price_amount": price,
        "currency": currency,
        "available": available,
        "cancellation_policy": _first(item, ["cancellationPolicy", "freeCancellation"]),
        "breakfast_included": breakfast if isinstance(breakfast, bool) else None,
        "source_url": _first(item, ["url", "link", "hotelUrl"]),
        "raw_payload": item,
    }


# ----------------------------------------------------------------------------
# Matching observations back to known competitor hotels
# ----------------------------------------------------------------------------
def _norm(s: Optional[str]) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _match_hotel(obs: Dict[str, Any], hotels: List[Dict[str, Any]]) -> Tuple[Optional[int], bool]:
    """Return (competitor_hotel_id, is_self) for an observation, matching by url then name."""
    obs_url = _norm(urlparse(obs.get("source_url") or "").path)
    obs_name = _norm(obs.get("hotel_name"))
    for h in hotels:
        h_url = _norm(urlparse(h.get("booking_url") or "").path)
        if obs_url and h_url and obs_url == h_url:
            return h["id"], h["is_self"]
    for h in hotels:
        h_name = _norm(h["name"])
        if obs_name and h_name and (obs_name in h_name or h_name in obs_name):
            return h["id"], h["is_self"]
    return None, False


# ----------------------------------------------------------------------------
# Scrape runs
# ----------------------------------------------------------------------------
def _recent_successful_run_exists(search_params: Dict[str, Any]) -> bool:
    """Duplicate-run guard: skip if an equivalent run succeeded within the dedup window."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM rateshop.pricing_scrape_runs
            WHERE status = 'succeeded'
              AND search_params->>'check_in' = %s
              AND (search_params->>'nights')::int = %s
              AND (search_params->>'adults')::int = %s
              AND (search_params->>'children')::int = %s
              AND started_at > now() - (%s || ' hours')::interval
            LIMIT 1
            """,
            (
                search_params["check_in"].isoformat() if isinstance(search_params["check_in"], date)
                else search_params["check_in"],
                search_params["nights"],
                search_params["adults"],
                search_params["children"],
                DEDUP_WINDOW_HOURS,
            ),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def _insert_run(actor_id: str, run_id: Optional[str], status: str, search_params: Dict[str, Any]) -> int:
    sp = dict(search_params)
    for k in ("check_in", "check_out"):
        if isinstance(sp.get(k), date):
            sp[k] = sp[k].isoformat()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO rateshop.pricing_scrape_runs (provider, actor_id, run_id, status, search_params)
            VALUES ('apify', %s, %s, %s, %s) RETURNING id
            """,
            (actor_id, run_id, status, Json(sp)),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return int(new_id)
    finally:
        conn.close()


def _finish_run(
    db_run_id: int,
    status: str,
    item_count: Optional[int] = None,
    cost_usd: Optional[float] = None,
    error_message: Optional[str] = None,
) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE rateshop.pricing_scrape_runs
            SET status = %s, item_count = %s, cost_usd = %s,
                error_message = %s, finished_at = now()
            WHERE id = %s
            """,
            (status, item_count, cost_usd, error_message, db_run_id),
        )
        conn.commit()
    finally:
        conn.close()


def start_scrape_run(
    check_in: date,
    nights: int = 1,
    adults: int = 2,
    children: int = 0,
    hotel_ids: Optional[List[int]] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    """Start ONE Apify run covering all selected hotels for a single stay.

    Returns {db_run_id, apify_run_id, status, skipped}.
    """
    currency = currency or DEFAULT_CURRENCY
    check_out = check_in + timedelta(days=nights)

    hotels = list_competitor_hotels(active_only=True)
    if hotel_ids:
        hotels = [h for h in hotels if h["id"] in set(hotel_ids)]
    if not hotels:
        raise ValueError("No active competitor hotels to scrape. Add some first.")
    if len(hotels) > MAX_COMPETITORS:
        hotels = hotels[:MAX_COMPETITORS]  # cost guard

    search_params = {
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "adults": adults,
        "children": children,
        "source": "booking",
        "hotel_ids": [h["id"] for h in hotels],
    }

    # Cost guard: don't re-run an equivalent search if one just succeeded.
    if _recent_successful_run_exists(search_params):
        return {"db_run_id": None, "apify_run_id": None, "status": "skipped", "skipped": True}

    client = ApifyClient(actor_id=os.getenv("APIFY_ACTOR_ID"))
    actor_input = build_booking_input(hotels, check_in, check_out, adults, children, currency)

    try:
        run = client.start_run(actor_input)
    except ApifyError as exc:
        db_run_id = _insert_run(client.actor_id, None, "failed", search_params)
        _finish_run(db_run_id, "failed", error_message=str(exc))
        raise

    db_run_id = _insert_run(client.actor_id, run.get("id"), "running", search_params)
    return {
        "db_run_id": db_run_id,
        "apify_run_id": run.get("id"),
        "status": "running",
        "skipped": False,
    }


def _load_run(db_run_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM rateshop.pricing_scrape_runs WHERE id = %s", (db_run_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _upsert_observations(db_run_id: int, observations: List[Dict[str, Any]], hotels: List[Dict[str, Any]]) -> int:
    if not observations:
        return 0
    conn = get_conn()
    inserted = 0
    try:
        cur = conn.cursor()
        for obs in observations:
            comp_id, is_self = _match_hotel(obs, hotels)
            cur.execute(
                """
                INSERT INTO rateshop.hotel_price_observations
                    (scrape_run_id, hotel_name, competitor_hotel_id, is_self, source,
                     check_in, check_out, nights, guests_adults, guests_children, room_type,
                     price_amount, currency, available, cancellation_policy, breakfast_included,
                     source_url, raw_payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (hotel_name, check_in, nights, guests_adults,
                             (COALESCE(room_type, '')), source, observed_on)
                DO UPDATE SET
                    price_amount = EXCLUDED.price_amount,
                    available = EXCLUDED.available,
                    currency = EXCLUDED.currency,
                    competitor_hotel_id = EXCLUDED.competitor_hotel_id,
                    is_self = EXCLUDED.is_self,
                    cancellation_policy = EXCLUDED.cancellation_policy,
                    breakfast_included = EXCLUDED.breakfast_included,
                    source_url = EXCLUDED.source_url,
                    raw_payload = EXCLUDED.raw_payload,
                    scrape_run_id = EXCLUDED.scrape_run_id,
                    scraped_at = now()
                """,
                (
                    db_run_id, obs["hotel_name"], comp_id, is_self, obs["source"],
                    obs["check_in"], obs["check_out"], obs["nights"], obs["guests_adults"],
                    obs["guests_children"], obs["room_type"], obs["price_amount"], obs["currency"],
                    obs["available"], obs["cancellation_policy"], obs["breakfast_included"],
                    obs["source_url"], Json(obs["raw_payload"]),
                ),
            )
            inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def sync_scrape_run(db_run_id: int) -> Dict[str, Any]:
    """Poll Apify for the run, and if finished, fetch + normalise + persist observations."""
    run_row = _load_run(db_run_id)
    if not run_row:
        raise ValueError(f"Scrape run {db_run_id} not found")
    apify_run_id = run_row.get("run_id")
    if not apify_run_id:
        _finish_run(db_run_id, "failed", error_message="No Apify run id stored")
        return {"status": "failed", "item_count": 0}

    client = ApifyClient(actor_id=run_row.get("actor_id"))
    try:
        run = client.get_run(apify_run_id)
    except ApifyError as exc:
        _finish_run(db_run_id, "failed", error_message=str(exc))
        return {"status": "failed", "error": str(exc)}

    status = (run.get("status") or "").upper()
    if status not in TERMINAL_OK and status not in TERMINAL_FAIL:
        return {"status": "running"}  # not finished yet

    cost = client.extract_cost_usd(run)

    if status in TERMINAL_FAIL:
        mapped = "timed_out" if status == "TIMED-OUT" else "failed"
        _finish_run(db_run_id, mapped, cost_usd=cost, error_message=f"Apify run {status}")
        return {"status": mapped}

    # SUCCEEDED -> fetch dataset
    dataset_id = run.get("defaultDatasetId")
    try:
        items = client.get_dataset_items(dataset_id) if dataset_id else []
    except ApifyError as exc:
        _finish_run(db_run_id, "failed", cost_usd=cost, error_message=str(exc))
        return {"status": "failed", "error": str(exc)}

    if not items:
        _finish_run(db_run_id, "empty", item_count=0, cost_usd=cost,
                    error_message="Actor returned an empty dataset")
        return {"status": "empty", "item_count": 0}

    sp = run_row["search_params"] or {}
    search_params = {
        "check_in": datetime.fromisoformat(sp["check_in"]).date(),
        "check_out": datetime.fromisoformat(sp["check_out"]).date(),
        "nights": sp["nights"],
        "adults": sp["adults"],
        "children": sp["children"],
        "source": sp.get("source", "booking"),
    }

    observations = []
    for it in items:
        try:
            obs = normalise_item(it, search_params=search_params, default_currency=DEFAULT_CURRENCY)
        except Exception:  # malformed item -> skip, keep going
            obs = None
        if obs:
            observations.append(obs)

    hotels = list_competitor_hotels()
    count = _upsert_observations(db_run_id, observations, hotels)
    _finish_run(db_run_id, "succeeded", item_count=count, cost_usd=cost)
    return {"status": "succeeded", "item_count": count, "cost_usd": cost}


def run_price_check(
    start_date: date,
    end_date: date,
    nights: int = 1,
    adults: int = 2,
    children: int = 0,
    hotel_ids: Optional[List[int]] = None,
    wait: bool = True,
    poll_timeout_secs: int = 180,
) -> List[Dict[str, Any]]:
    """Start (and optionally wait+sync) one scrape per check-in date in the range.

    Used by the dashboard button and by the scheduled job. Applies the date-count
    and horizon safeguards.
    """
    import time

    # Horizon safeguard.
    horizon_limit = date.today() + timedelta(days=MAX_HORIZON_DAYS)
    if end_date > horizon_limit:
        end_date = horizon_limit

    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += timedelta(days=1)
    if len(dates) > MAX_DATES_PER_MANUAL_RUN:
        dates = dates[:MAX_DATES_PER_MANUAL_RUN]  # cost guard

    results = []
    for ci in dates:
        try:
            started = start_scrape_run(ci, nights, adults, children, hotel_ids)
        except Exception as exc:
            results.append({"check_in": ci.isoformat(), "status": "failed", "error": str(exc)})
            continue

        if started.get("skipped"):
            results.append({"check_in": ci.isoformat(), "status": "skipped"})
            continue

        if wait and started.get("db_run_id"):
            deadline = time.monotonic() + poll_timeout_secs
            outcome = {"status": "running"}
            while time.monotonic() < deadline:
                outcome = sync_scrape_run(started["db_run_id"])
                if outcome["status"] != "running":
                    break
                time.sleep(6)
            results.append({"check_in": ci.isoformat(), **outcome})
        else:
            results.append({"check_in": ci.isoformat(), **started})
    return results


# ----------------------------------------------------------------------------
# Insights + recommendations
# ----------------------------------------------------------------------------
def _median_trend(check_in: date, nights: int, adults: int) -> Optional[float]:
    """% change of competitor median between the latest and the previous scrape day.

    Negative = prices falling. Returns None if we have fewer than 2 scrape days.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH per_day AS (
                SELECT observed_on,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY price_amount)
                         FILTER (WHERE available IS NOT FALSE) AS med
                FROM rateshop.hotel_price_observations
                WHERE check_in = %s AND nights = %s AND guests_adults = %s AND is_self = false
                GROUP BY observed_on
                ORDER BY observed_on DESC
                LIMIT 2
            )
            SELECT med FROM per_day
            """,
            (check_in, nights, adults),
        )
        rows = [r[0] for r in cur.fetchall() if r[0] is not None]
        if len(rows) < 2 or not rows[1]:
            return None
        latest, prev = float(rows[0]), float(rows[1])
        return (latest - prev) / prev if prev else None
    finally:
        conn.close()


def recommend(row: Dict[str, Any], median_trend: Optional[float] = None) -> str:
    """Suggested action for one insights row, following the documented rules."""
    elbitat = row.get("elbitat_price")
    elbitat = float(elbitat) if elbitat is not None else None
    elbitat_avail = row.get("elbitat_available")
    median = row.get("competitor_median")
    median = float(median) if median is not None else None
    avail_count = row.get("competitor_available_count") or 0
    total = row.get("competitor_total_count") or 0

    high_availability = total > 0 and avail_count >= math.ceil(HIGH_AVAIL_RATIO * total)
    mostly_sold_out = total > 0 and avail_count <= math.floor(SOLD_OUT_RATIO * total)

    # Rule 5: no Elbitat price but competitors have prices -> visibility/OTA issue.
    if elbitat is None and median is not None:
        return "🔴 Visibility / OTA listing issue — Elbitat has no price for these dates while competitors do"

    if elbitat is None or median is None:
        return "ℹ️ Not enough data"

    # Rule 2: competitors mostly sold out and Elbitat available -> raise price.
    if mostly_sold_out and elbitat_avail is not False:
        return "🟢 Competitors mostly sold out — strong demand, consider raising price"

    # Rule 4: falling prices + plenty of availability -> weak demand.
    if median_trend is not None and median_trend < -FALLING_PRICE_PCT and high_availability:
        return "⚠️ Weak market demand — competitor prices falling with high availability"

    # Rule 1: >15% above median with high availability -> review price / add package.
    if elbitat > median * (1 + ABOVE_MARKET_PCT) and high_availability:
        return "🟠 ~15%+ above market with high availability — review price or add a package"

    # Rule 3: below median and tight market -> increase price.
    if elbitat < median and not high_availability:
        return "🟢 Below market and availability is tight — consider increasing price"

    return "✅ In line with the market — hold"


def get_insights(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    nights: Optional[int] = None,
    adults: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return insights rows (from the view) enriched with a suggested action."""
    clauses, params = [], []
    if start_date:
        clauses.append("check_in >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("check_in <= %s")
        params.append(end_date)
    if nights is not None:
        clauses.append("nights = %s")
        params.append(nights)
    if adults is not None:
        clauses.append("guests_adults = %s")
        params.append(adults)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM rateshop.pricing_insights{where} ORDER BY check_in", params)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    for r in rows:
        trend = _median_trend(r["check_in"], r["nights"], r["guests_adults"])
        r["median_trend_pct"] = round(trend * 100, 1) if trend is not None else None
        r["recommendation"] = recommend(r, trend)
    return rows


def get_price_matrix(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    nights: Optional[int] = None,
    adults: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return the latest observed price for every hotel on every check-in date.

    One row per (check_in, hotel) with the most recent observation, so the UI can pivot it
    into a grid of dates x hotels. Sold-out dates come back with price = None.
    """
    clauses, params = [], []
    if start_date:
        clauses.append("check_in >= %s")
        params.append(start_date)
    if end_date:
        clauses.append("check_in <= %s")
        params.append(end_date)
    if nights is not None:
        clauses.append("nights = %s")
        params.append(nights)
    if adults is not None:
        clauses.append("guests_adults = %s")
        params.append(adults)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT DISTINCT ON (check_in, hotel_name)
                check_in, hotel_name, is_self, nights, guests_adults,
                price_amount, currency, available, observed_on
            FROM rateshop.hotel_price_observations
            {where}
            ORDER BY check_in, hotel_name, observed_on DESC, scraped_at DESC
            """,
            params,
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_recent_runs(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM rateshop.pricing_scrape_runs ORDER BY started_at DESC LIMIT %s",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
