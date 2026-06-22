import os
import pandas as pd
import streamlit as st
from datetime import date, timedelta

# Single-process mode: use backend services directly (no FastAPI required)
# Ensure repo root is on sys.path so `backend.app` imports work when running `streamlit run ui/streamlit_app.py`
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.competitor_service import (  # noqa: E402
    init_db,
    add_competitor,
    list_competitors,
    delete_competitor,
)
from backend.app.services.pricing_service import (  # noqa: E402
    create_run,
    run_pricing,
    save_recommendations,
    get_recommendations,
)
from backend.app.core.config import AppConfig  # noqa: E402
from backend.app.services.report_export import build_excel_report  # noqa: E402

# Initialize local DB (SQLite) once
init_db()

# Page configuration
st.set_page_config(
    page_title="Hotel Pricing Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 500;
    }
    .competitor-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #f0f2f6;
        margin: 10px 0;
    }
    .success-box {
        padding: 10px;
        border-radius: 5px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 10px;
        border-radius: 5px;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# --------------------
# Simple login gate
# --------------------
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False


def _show_login():
    st.title("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password")


if not st.session_state["authenticated"]:
    _show_login()
    st.stop()

# Sidebar logout
with st.sidebar:
    st.caption("Logged in")
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()

# Main title
st.title("🏨 Hotel Pricing Agent")

# Create tabs for different sections
# Add a new tab for competitor price upload/analysis
tab1, tab_comp, tab4, tab5 = st.tabs([
    "📊 Pricing Dashboard",
    "🏢 Competitors",
    "📈 Rate Shopping",
    "⚙️ Settings",
])

# ==================== TAB 1: PRICING DASHBOARD ====================
with tab1:
    st.header("💶 Pricing recommendations")
    st.caption(
        "Suggests Elbitat rates from the **latest scraped competitor median**. "
        "Choose how far above or below the median you want to price."
    )

    cfg_obj = AppConfig()
    currency = cfg_obj.currency
    try:
        min_rate = float(cfg_obj.cfg.min_rate)
        max_rate = float(cfg_obj.cfg.max_rate)
    except Exception:
        min_rate, max_rate = 0.0, 1_000_000.0

    try:
        from backend.app.core import db as _pd_db  # noqa: E402
        from backend.app.services import rate_shopping_service as _pd_rss  # noqa: E402
        _pd_ok = _pd_db.is_configured()
        _pd_err = None
    except Exception as _e:  # pragma: no cover
        _pd_ok, _pd_err = False, str(_e)

    if not _pd_ok:
        st.warning(
            "Recommendations use the scraped competitor data, so set up rate shopping first "
            "(`SUPABASE_DB_URL`). See the **📈 Rate Shopping** tab."
            + (f"\n\n{_pd_err}" if _pd_err else "")
        )
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            p_start = st.date_input("From", value=date.today(), key="pd_start")
        with c2:
            p_end = st.date_input("To", value=date.today() + timedelta(days=90), key="pd_end")
        with c3:
            p_nights = st.selectbox("Stay length", options=[1, 2, 3, 7], index=1, key="pd_nights")
        with c4:
            p_adults = st.selectbox("Adults", options=[1, 2, 3, 4], index=1, key="pd_adults")
        with c5:
            p_basis = st.radio("Price basis", options=["Per night", "Total stay"], index=0, key="pd_basis")
        per_night = p_basis == "Per night"

        position = st.slider(
            "Target vs competitor median (%)", min_value=-30, max_value=30, value=0, step=1, key="pd_position",
            help="0 = match the median. +10 = price 10% above the median. -10 = 10% below.",
        )
        st.caption(
            f"Guardrails from config/settings.yaml: min {currency}{min_rate:.0f} / max {currency}{max_rate:.0f} per night. "
            "Recommendations are clamped to this range."
        )

        if st.button("💶 Calculate recommendations", type="primary", use_container_width=True, key="pd_calc_btn"):
            st.session_state["pd_calc"] = True
        _pd_show = bool(st.session_state.get("pd_calc"))

        insights = []
        if _pd_show:
            try:
                insights = _pd_rss.get_insights(
                    start_date=p_start, end_date=p_end, nights=int(p_nights), adults=int(p_adults)
                )
            except Exception as e:
                st.error(f"Could not load competitor data: {e}")

        if not _pd_show:
            st.info("Set your options above, then click **💶 Calculate recommendations**.")
        elif not insights:
            st.info("No competitor data for these dates yet. Collect prices in the 📈 Rate Shopping tab.")
        else:
            factor = 1 + position / 100.0

            def _disp(per_night_value, nights):
                if per_night_value is None:
                    return None
                return round(per_night_value if per_night else per_night_value * nights, 2)

            rows = []
            for r in insights:
                med_total = r.get("competitor_median")
                if med_total is None:
                    continue
                n = r.get("nights") or 1
                med_pn = float(med_total) / n
                rec_pn = max(min_rate, min(med_pn * factor, max_rate))  # clamp to guardrails
                cmin = r.get("competitor_min")
                cmax = r.get("competitor_max")
                cur = r.get("elbitat_price")
                cur_pn = float(cur) / n if cur is not None else None
                rec_disp = _disp(rec_pn, n)
                cur_disp = _disp(cur_pn, n)
                rows.append({
                    "date": str(r["check_in"]),
                    "competitor_min": _disp(float(cmin) / n, n) if cmin is not None else None,
                    "competitor_median": _disp(med_pn, n),
                    "competitor_max": _disp(float(cmax) / n, n) if cmax is not None else None,
                    "current_elbitat": cur_disp,
                    "recommended": rec_disp,
                    "change_vs_current": (round(rec_disp - cur_disp, 2) if cur_disp is not None else None),
                })

            df = pd.DataFrame(rows)
            if df.empty:
                st.info("No competitor medians available for these dates.")
            else:
                basis_lbl = "per night" if per_night else "total stay"
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Dates", len(df))
                with m2:
                    st.metric(f"Avg recommended ({basis_lbl})", f"{currency}{df['recommended'].mean():.2f}")
                with m3:
                    chg = df["change_vs_current"].dropna()
                    st.metric("Avg change vs current", f"{currency}{chg.mean():.2f}" if len(chg) else "—")

                money = lambda label: st.column_config.NumberColumn(label, format="€%.2f")
                st.dataframe(
                    df, use_container_width=True, hide_index=True,
                    column_config={
                        "date": "Date",
                        "competitor_min": money("Comp min"),
                        "competitor_median": money("Comp median"),
                        "competitor_max": money("Comp max"),
                        "current_elbitat": money("Current Elbitat"),
                        "recommended": money("Recommended"),
                        "change_vs_current": money("Δ vs current"),
                    },
                )

                try:
                    xlsx = build_excel_report({"Recommended rates": df})
                    st.download_button(
                        "⬇️ Download recommendations (Excel)",
                        data=xlsx,
                        file_name=f"elbitat_recommendations_{p_start}_{p_end}_{position:+d}pct.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary", use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Could not build Excel file: {e}")

                st.caption(
                    "ℹ️ Pushing these rates to Booking.com requires the Simple Booking integration (parked for now). "
                    "For now, use the Excel export or enter them in your channel manager."
                )

# ==================== TAB: COMPETITORS ====================
with tab_comp:
    st.header("🏢 Competitors")
    st.caption("The hotels tracked for rate shopping. Stored permanently in Supabase.")

    try:
        from backend.app.core import db as _cm_db  # noqa: E402
        from backend.app.services import rate_shopping_service as _cm_rss  # noqa: E402
        _cm_ok, _cm_err = True, None
    except Exception as _e:  # pragma: no cover
        _cm_ok, _cm_err = False, str(_e)

    if not _cm_ok:
        st.error(f"Dependencies unavailable. Run `pip install -r requirements.txt`.\n\n{_cm_err}")
    elif not _cm_db.is_configured():
        st.warning("⚙️ Set `SUPABASE_DB_URL` to manage competitors (see the Rate Shopping tab for setup).")
    else:
        st.markdown(
            "Add **Elbitat** (tick *This is Elbitat*) plus 5–15 competitors. "
            "A Booking.com hotel-page URL gives the most precise scrape."
        )
        with st.expander("➕ Add hotel", expanded=False):
            with st.form("cm_add_hotel", clear_on_submit=True):
                h_name = st.text_input("Name*", placeholder="e.g., Hotel Hermitage")
                h_url = st.text_input("Booking.com URL", placeholder="https://www.booking.com/hotel/it/...")
                h_loc = st.text_input("Location", value="Isola d'Elba")
                h_self = st.checkbox("This is Elbitat (self)", value=False)
                h_active = st.checkbox("Active", value=True)
                h_notes = st.text_input("Notes", placeholder="optional")
                if st.form_submit_button("Add hotel", type="primary"):
                    if not h_name:
                        st.error("Name is required.")
                    else:
                        try:
                            _cm_rss.add_competitor_hotel(
                                name=h_name, booking_url=h_url or None, location=h_loc or None,
                                active=bool(h_active), is_self=bool(h_self), notes=h_notes or None,
                            )
                            st.success(f"Added {h_name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        st.divider()
        try:
            _cm_hotels = _cm_rss.list_competitor_hotels()
        except Exception as e:
            _cm_hotels = []
            st.error(f"Could not load hotels: {e}")

        if not _cm_hotels:
            st.info("No hotels yet. Add Elbitat (as *self*) and a few competitors above.")
        else:
            for h in _cm_hotels:
                c1, c2, c3 = st.columns([5, 2, 1])
                with c1:
                    tag = "⭐ SELF" if h["is_self"] else ("🟢" if h["active"] else "🔴")
                    st.markdown(f"**{tag} {h['name']}**" + (f" — [link]({h['booking_url']})" if h.get("booking_url") else ""))
                    if h.get("location"):
                        st.caption(h["location"])
                with c2:
                    if st.button("Toggle active", key=f"cm_toggle_{h['id']}"):
                        _cm_rss.update_competitor_hotel(h["id"], {"active": not h["active"]})
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"cm_del_{h['id']}"):
                        _cm_rss.delete_competitor_hotel(int(h["id"]))
                        st.rerun()


# ==================== TAB 4: RATE SHOPPING ====================
with tab4:
    st.header("Rate Shopping — Elbitat vs Competitors")
    st.caption("Live competitor pricing scraped via Apify (server-side) and stored in Supabase.")

    # Lazy imports so the other tabs still work if Supabase/psycopg2 isn't configured locally.
    try:
        from backend.app.core import db as _rs_db  # noqa: E402
        from backend.app.services import rate_shopping_service as rss  # noqa: E402
        _rs_import_ok = True
        _rs_import_err = None
    except Exception as _e:  # pragma: no cover
        _rs_import_ok = False
        _rs_import_err = str(_e)

    if not _rs_import_ok:
        st.error(
            "Rate-shopping dependencies are not available. Install requirements "
            f"(`pip install -r requirements.txt`).\n\nDetails: {_rs_import_err}"
        )
    elif not _rs_db.is_configured():
        st.warning(
            "⚙️ Rate shopping is not configured yet. Set the following secrets/env vars:\n\n"
            "- `SUPABASE_DB_URL` — Supabase Transaction pooler connection string\n"
            "- `APIFY_TOKEN` — your Apify API token (kept server-side)\n"
            "- `APIFY_ACTOR_ID` — defaults to `voyager/booking-scraper`\n\n"
            "See `.env.example` and `RATE_SHOPPING_GUIDE.md`."
        )
    else:
        # ---------------- 1. Choose dates ----------------
        st.markdown("**1. Choose dates & options**")
        ic1, ic2, ic3, ic4, ic5 = st.columns(5)
        with ic1:
            in_start = st.date_input("From", value=date.today(), key="rs_in_start")
        with ic2:
            in_end = st.date_input("To", value=date.today() + timedelta(days=90), key="rs_in_end")
        with ic3:
            in_nights = st.selectbox("Stay length", options=["all", 1, 2, 3, 7], index=0, key="rs_in_nights")
        with ic4:
            in_adults = st.selectbox("Adults", options=[1, 2, 3, 4], index=1, key="rs_adults")
        with ic5:
            price_basis = st.radio(
                "Price basis", options=["Per night", "Total stay"], index=0, key="rs_price_basis",
                help="Booking.com returns the TOTAL price for the stay. 'Per night' divides it by the number of nights.",
            )
        per_night = price_basis == "Per night"

        # ---------------- Optional: collect fresh prices ----------------
        with st.expander("🔄 Need fresh prices now? Collect from Booking.com for the dates above"):
            st.caption(
                "Prices are collected automatically every week — use this only for an on-demand refresh. "
                f"Cost guards: ≤{rss.MAX_DATES_PER_MANUAL_RUN} dates/run, ≤{rss.MAX_COMPETITORS} competitors, "
                f"duplicate searches within {rss.DEDUP_WINDOW_HOURS}h are skipped."
            )
            in_children = st.number_input("Children", min_value=0, max_value=6, value=0, key="rs_children")
            fb1, fb2 = st.columns(2)
            with fb1:
                if st.button("🔄 Collect prices", type="primary", use_container_width=True):
                    if in_start > in_end:
                        st.error("'From' must be on or before 'To'.")
                    else:
                        nights_list = [1, 2] if in_nights == "all" else [int(in_nights)]
                        with st.spinner("Starting Apify runs and waiting briefly…"):
                            try:
                                results = []
                                for _n in nights_list:
                                    results += rss.run_price_check(
                                        start_date=in_start, end_date=in_end, nights=_n,
                                        adults=int(in_adults), children=int(in_children),
                                        wait=True, poll_timeout_secs=90,
                                    )
                                ok = sum(1 for r in results if r.get("status") == "succeeded")
                                running = sum(1 for r in results if r.get("status") == "running")
                                st.success(f"Loaded {ok}/{len(results)} date-runs.")
                                if running:
                                    st.info(f"⏳ {running} still running on Apify — click 'Sync latest' in ~1 min.")
                            except Exception as e:
                                st.error(f"Error: {e}")
            with fb2:
                if st.button("🔁 Sync latest", use_container_width=True):
                    with st.spinner("Checking Apify for finished runs…"):
                        try:
                            synced = rss.sync_pending_runs()
                            if synced:
                                done = sum(1 for s in synced if s.get("status") == "succeeded")
                                still = sum(1 for s in synced if s.get("status") == "running")
                                st.success(f"Checked {len(synced)}: {done} loaded, {still} still running.")
                            else:
                                st.info("No pending runs — all synced.")
                        except Exception as e:
                            st.error(f"Error: {e}")

        st.divider()
        st.markdown("**2. Your report** — review below and download as Excel")
        if st.button("📊 Show / refresh report", type="primary", use_container_width=True, key="rs_show_btn"):
            st.session_state["rs_show"] = True
        _rs_show = bool(st.session_state.get("rs_show"))
        if not _rs_show:
            st.info("Choose your dates above, then click **📊 Show / refresh report** to load the data.")

        idf_export = None   # populated below; used by the Excel download
        grid_export = None

        insights = []
        if _rs_show:
            try:
                insights = rss.get_insights(
                    start_date=in_start, end_date=in_end,
                    nights=None if in_nights == "all" else int(in_nights),
                    adults=int(in_adults),
                )
            except Exception as e:
                st.error(f"Could not load insights: {e}")

        if not insights:
            if _rs_show:
                st.info("No data for these dates yet. Use '🔄 Collect prices' above, or wait for the weekly update.")
        else:
            idf = pd.DataFrame(insights)
            price_cols = ["elbitat_price", "competitor_min", "competitor_median", "competitor_max"]
            if per_night and "nights" in idf.columns:
                for col in price_cols:
                    if col in idf.columns:
                        idf[col] = (pd.to_numeric(idf[col], errors="coerce") / idf["nights"]).round(2)
            st.caption(f"Prices shown **{'per night' if per_night else 'as total for the stay'}**.")
            cols = [
                "check_in", "nights", "elbitat_price", "competitor_min", "competitor_median",
                "competitor_max", "competitor_available_count", "elbitat_position",
                "median_trend_pct", "recommendation",
            ]
            idf = idf[[c for c in cols if c in idf.columns]]
            idf_export = idf.copy()
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Dates analysed", len(idf))
            with m2:
                above = (idf["elbitat_position"] == "above").sum() if "elbitat_position" in idf else 0
                st.metric("Dates priced above market", int(above))
            with m3:
                flags = idf["recommendation"].str.startswith(("🔴", "🟠", "⚠️")).sum() if "recommendation" in idf else 0
                st.metric("Dates needing attention", int(flags))
            st.dataframe(
                idf, use_container_width=True, hide_index=True,
                column_config={
                    "check_in": "Date",
                    "elbitat_price": "Elbitat",
                    "competitor_min": "Comp min",
                    "competitor_median": "Comp median",
                    "competitor_max": "Comp max",
                    "competitor_available_count": "Comps avail",
                    "elbitat_position": "Position",
                    "median_trend_pct": "Median Δ%",
                    "recommendation": "Suggested action",
                },
            )

        st.divider()

        # ---------------- Per-hotel price grid ----------------
        st.subheader("🏨 Price per hotel, per day")
        st.caption(
            f"Latest scraped price ({'per night' if per_night else 'total for the stay'}) for each hotel "
            "on each check-in date. Blank = sold out / no availability."
        )
        matrix = []
        if _rs_show:
            try:
                matrix = rss.get_price_matrix(
                    start_date=in_start, end_date=in_end,
                    nights=None if in_nights == "all" else int(in_nights),
                    adults=int(in_adults),
                )
            except Exception as e:
                st.error(f"Could not load price grid: {e}")

        if not matrix:
            if _rs_show:
                st.info("No per-hotel observations yet for this filter.")
        else:
            mdf = pd.DataFrame(matrix)
            if per_night and "nights" in mdf.columns:
                mdf["price_amount"] = (pd.to_numeric(mdf["price_amount"], errors="coerce") / mdf["nights"]).round(2)
            # Put Elbitat first among the columns.
            order = (
                mdf[["hotel_name", "is_self"]].drop_duplicates()
                .sort_values(["is_self", "hotel_name"], ascending=[False, True])["hotel_name"].tolist()
            )
            grid = mdf.pivot_table(
                index="check_in", columns="hotel_name", values="price_amount", aggfunc="first"
            )
            grid = grid.reindex(columns=[c for c in order if c in grid.columns])
            grid = grid.sort_index()
            st.dataframe(grid, use_container_width=True)
            grid_export = grid.copy()

        # ---------------- Excel download (formatted) ----------------
        if idf_export is not None or grid_export is not None:
            basis_label = "per night" if per_night else "total stay"
            try:
                xlsx_bytes = build_excel_report({
                    "Elbitat vs competitors": idf_export,
                    "Price per hotel": grid_export,
                })
                fname = f"elbitat_rate_shopping_{in_start}_{in_end}_{basis_label.replace(' ', '-')}.xlsx"
                st.download_button(
                    "⬇️ Download Excel report (formatted)",
                    data=xlsx_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
                st.caption(f"Two sheets — comparison + per-hotel grid. Prices {basis_label}.")
            except Exception as e:
                st.error(f"Could not build Excel file: {e}")

        st.divider()

        # ---------------- Recent runs ----------------
        with st.expander("🛰️ Recent scrape runs"):
            try:
                runs = rss.list_recent_runs(limit=15) if _rs_show else []
                if runs:
                    rdf = pd.DataFrame(runs)[
                        [c for c in ["id", "status", "item_count", "cost_usd", "started_at", "finished_at", "error_message"]
                         if c in pd.DataFrame(runs).columns]
                    ]
                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                else:
                    st.caption("No runs yet." if _rs_show else "Click 'Show / refresh report' above to load.")
            except Exception as e:
                st.error(f"Could not load runs: {e}")

# ==================== TAB 5: SETTINGS ====================
with tab5:
    st.header("Configuration Settings")
    st.markdown("Configure your hotel pricing parameters and system settings.")

    cfg_obj = AppConfig()
    st.divider()

    col_set1, col_set2 = st.columns(2)

    with col_set1:
        st.subheader("🏨 Hotel Information")
        st.text_input("Currency", value=str(cfg_obj.currency), disabled=True)
        st.text_input("Property ID", value=str(cfg_obj.sb_property_id or ""), disabled=True)
        st.text_input("Rate Plan ID", value=str(cfg_obj.sb_rate_plan_id or ""), disabled=True)

    with col_set2:
        st.subheader("📊 Default Parameters")
        st.number_input("Default Horizon (days)", value=int(cfg_obj.horizon_days), disabled=True)
        st.number_input("Default Occupancy", value=int(cfg_obj.occupancy), disabled=True)

    st.divider()
    st.info("💡 To modify these settings, edit the `config/settings.yaml` file.")

# Footer
st.divider()
st.markdown("---")
st.markdown("🏨 **Hotel Pricing Agent** | Powered by AI & Market Intelligence")