# 📈 Rate Shopping (Competitor Pricing Intelligence)

Track Elbitat's price/availability against a small fixed set of competitors on
Booking.com, scraped with **Apify** (server-side) and stored in **Supabase Postgres**.

All scraping is server-side. `APIFY_TOKEN` and `SUPABASE_DB_URL` are never exposed to the
browser.

---

## 1. Architecture (as built)

```
Streamlit UI ("📈 Rate Shopping" tab)        scripts/sync_apify.py (cron / CLI)
        │                                              │
        └──────────────┬───────────────────────────────┘
                       ▼
        backend/app/services/rate_shopping_service.py
          • competitor CRUD     • start/sync runs
          • normalisation       • insights + recommendations
          • cost safeguards
            │                                   │
            ▼                                   ▼
  backend/app/clients/apify_client.py    backend/app/core/db.py
        (Apify REST, requests)            (Supabase Postgres, psycopg2)
            │                                   │
            ▼                                   ▼
        Apify actor                       rateshop.* tables + view
   (voyager/booking-scraper)
```

The legacy SQLite tables (competitors/runs/recommendations) are untouched. Rate-shopping
data lives in the **`rateshop`** schema in Supabase so it persists across Streamlit Cloud
redeploys.

---

## 2. Files changed / added

**Added**
- `backend/app/core/db.py` — Supabase Postgres connection helper.
- `backend/app/clients/apify_client.py` — server-side Apify REST client.
- `backend/app/services/rate_shopping_service.py` — the feature (CRUD, runs, normalise, insights, safeguards).
- `scripts/sync_apify.py` — CLI for seeding + scheduled scraping + syncing.
- `config/competitors.example.yaml` — competitor seed template.
- `.github/workflows/daily-scrape.yml` — daily cron (GitHub Actions).
- `RATE_SHOPPING_GUIDE.md` — this file.

**Modified**
- `ui/streamlit_app.py` — new "📈 Rate Shopping" tab.
- `requirements.txt` — added `psycopg2-binary`.
- `.env.example` — added Apify/Supabase/safeguard vars.

**Database migration** (already applied to Supabase project `xdobtmfkbdgenzmtpmlv`, schema `rateshop`):
`competitor_hotels`, `pricing_scrape_runs`, `hotel_price_observations`, plus the
`pricing_insights` view, the `uq_obs_dedup` unique index, and RLS enabled on all tables.

---

## 3. Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `APIFY_TOKEN` | ✅ | Apify API token (server-side only) |
| `APIFY_ACTOR_ID` | ✅ (defaulted) | Booking.com actor, default `voyager/booking-scraper` |
| `SUPABASE_DB_URL` | ✅ | Supabase **Transaction pooler** connection string (port 6543) |
| `PRICING_DEFAULT_CURRENCY` | optional | Default `EUR` |
| `APIFY_WEBHOOK_SECRET` | optional | Only if you add a webhook receiver (see §10) |
| `RATESHOP_MAX_HORIZON_DAYS` | optional | Default `120` |
| `RATESHOP_MAX_COMPETITORS` | optional | Default `15` |
| `RATESHOP_MAX_DATES_PER_MANUAL_RUN` | optional | Default `14` |
| `RATESHOP_DEDUP_WINDOW_HOURS` | optional | Default `12` |

Get the `SUPABASE_DB_URL` from: **Supabase Dashboard → Project Settings → Database →
Connection string → Transaction pooler**. It looks like:

```
postgresql://postgres.xdobtmfkbdgenzmtpmlv:YOUR_DB_PASSWORD@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
```

On **Streamlit Cloud**, put these under *App → Settings → Secrets* (TOML), e.g.:

```toml
APIFY_TOKEN = "apify_api_xxx"
APIFY_ACTOR_ID = "voyager/booking-scraper"
SUPABASE_DB_URL = "postgresql://postgres.xxx:...@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
PRICING_DEFAULT_CURRENCY = "EUR"
```

---

## 4. Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in APIFY_TOKEN and SUPABASE_DB_URL
streamlit run ui/streamlit_app.py
```

Open the **📈 Rate Shopping** tab. If config is missing, the tab shows exactly what to set.

---

## 5. Test with one competitor

1. In the **Rate Shopping** tab → *Add hotel*:
   - Add **Elbitat** with its Booking.com URL, tick **This is Elbitat (self)**.
   - Add **one** competitor with its Booking.com URL.
2. Under *Run a price check*: pick a check-in ~2 weeks out, **To = same date**, Nights = 1.
3. Click **Run price check**. It starts one Apify run and waits for results.
4. Scroll to *Elbitat vs competitors* — you'll see the date row with Elbitat price,
   competitor min/median/max, and a suggested action.

CLI equivalent:
```bash
python scripts/sync_apify.py seed --file config/competitors.yaml   # optional bulk add
python scripts/sync_apify.py scrape --days 1 --nights 1 --adults 2
```

---

## 6. Trigger a scrape manually

- **UI:** the *Run price check* button (range capped at `RATESHOP_MAX_DATES_PER_MANUAL_RUN`).
- **CLI:** `python scripts/sync_apify.py scrape --days 90 --nights 1,2 --adults 2`
- **Resume long runs:** `python scripts/sync_apify.py sync-pending`

---

## 7. Schedule daily scraping

Streamlit Cloud has **no cron**, so scheduling is external. Two supported options:

**A. GitHub Actions (included).** `.github/workflows/daily-scrape.yml` runs daily at 04:30
UTC. Add repo secrets (*Settings → Secrets and variables → Actions*):
`APIFY_TOKEN`, `APIFY_ACTOR_ID`, `SUPABASE_DB_URL`. It runs:
```
python scripts/sync_apify.py scrape --days 90 --nights 1,2 --adults 2
```
Defaults: next 90 days, 1- & 2-night stays, 2 adults. Edit the cron line or args to taste.

**B. Apify native scheduler (lowest friction, no GitHub).** In the Apify console you can
schedule the actor itself. Because the dashboard pulls from Supabase (not Apify), you'd
still need a sync step — so option A is recommended. If you prefer Apify scheduling, point
its schedule at the actor with a saved input and then run `sync-pending` from any cron.

---

## 8. Cost control (built in)

- **Horizon cap** — requests beyond `RATESHOP_MAX_HORIZON_DAYS` (120) are trimmed.
- **Competitor cap** — at most `RATESHOP_MAX_COMPETITORS` (15) hotels per run.
- **Duplicate suppression** — an equivalent search that already *succeeded* within
  `RATESHOP_DEDUP_WINDOW_HOURS` (12h) is **skipped** (status `skipped`).
- **Manual date cap** — UI runs limited to `RATESHOP_MAX_DATES_PER_MANUAL_RUN` (14) dates.
- **Server-side actor timeout** — each Apify run is capped (default 600s) so a stuck run
  cannot bill indefinitely.
- **Daily, not hourly** — the workflow runs once/day. Don't lower without reason.
- **Cost logging** — each run stores `cost_usd` (from Apify) and `item_count`, shown under
  *Recent scrape runs* and summed by the CLI.

> Rough cost shape: one Apify run per (check-in date × stay length). 90 days × 2 stays =
> 180 runs/day. Reduce by shrinking `--days`, using one stay length, or scraping
> far-out dates less often.

---

## 9. Error handling

| Situation | Behaviour |
|---|---|
| Apify API error on start | Run saved as `failed` with the message; UI/CLI surfaces it |
| Actor timeout | Run marked `timed_out` |
| Empty dataset | Run marked `empty`, `item_count = 0` |
| Hotel not found / sold-out date | No price → observation stored with `available = false` |
| Malformed scraped price | `_to_float_price` returns `None`; row skipped or stored unavailable |
| Currency string variants | Parsed (`€1.234,50`, `1,234.50`, `EUR 120`) |
| Duplicate observations | `uq_obs_dedup` + `ON CONFLICT … DO UPDATE` (idempotent re-sync) |
| Missing config | Tab shows setup instructions instead of crashing |

---

## 10. Webhook endpoint (optional — and why it's omitted)

The app runs **Streamlit-only** (no always-on HTTP server), so it cannot receive Apify
webhooks directly. The supported pattern is **start → poll → sync** (used by both the UI
button and the cron job), which needs no inbound endpoint.

If you later add a FastAPI deployment, wire an endpoint that:
1. validates the `APIFY_WEBHOOK_SECRET`,
2. reads the finished `runId`,
3. looks up the matching `pricing_scrape_runs` row and calls `sync_scrape_run(db_run_id)`.

---

## 11. Assumptions about the Apify actor output

Default actor: **`voyager/booking-scraper`**. The normaliser (`normalise_item` in
`rate_shopping_service.py`) maps these fields with fallbacks — **adapt them if your actor
differs**; the section is marked `>>> ADAPT THESE MAPPINGS <<<`:

| Observation field | Looked-up keys (first non-empty wins) |
|---|---|
| hotel_name | `name`, `hotelName`, `title` |
| price_amount | `price`, `priceText`, `minPrice`, `totalPrice` |
| currency | `currency`, `currencyCode` → else `PRICING_DEFAULT_CURRENCY` |
| available | `available`/`isAvailable`/`hasAvailability`, else inferred from a price |
| room_type | `roomType`, `roomName`, `unitType` |
| source_url | `url`, `link`, `hotelUrl` |
| breakfast_included | `breakfastIncluded`, `breakfast`, `mealPlan` |

The **stay context** (check-in/out, nights, guests) comes from the run's `search_params`,
not the item, because actors don't reliably echo the searched dates. Every raw item is
stored in `raw_payload` (JSONB) for debugging and re-mapping.

---

## 12. Manual Apify setup checklist

1. Create an Apify account → **Settings → Integrations → API token**; set `APIFY_TOKEN`.
2. Confirm the actor name. Default `voyager/booking-scraper`. If you pick a different
   Booking.com / Google Hotels actor, set `APIFY_ACTOR_ID` and review §11 mappings.
3. (Recommended) Run the actor once manually in the Apify console with a single hotel URL
   to confirm the output field names match §11; tweak `normalise_item` if needed.
4. Collect each competitor's **Booking.com hotel URL** and add them in the app (or seed
   file). URLs give precise per-hotel scraping; names fall back to search.
5. Add the env vars / Streamlit secrets / GitHub secrets (§3, §7).
