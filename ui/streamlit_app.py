import os
import io
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

# Columns that are numeric but NOT money (so we don't apply a € format to them).
_NON_MONEY_NUMERIC = {
    "nights", "guests_adults", "guests_children",
    "competitor_available_count", "competitor_total_count", "median_trend_pct",
}


def build_excel_report(sheets: dict) -> bytes:
    """Build a formatted multi-sheet .xlsx from {sheet_name: DataFrame}.

    Bold header row, frozen header, autofilter, auto-fit column widths, and a € number
    format on price columns. Returns the file as bytes for st.download_button.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#1F4E78", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        money_fmt = wb.add_format({"num_format": "€#,##0.00"})

        for raw_name, df in sheets.items():
            name = (str(raw_name)[:31]) or "Sheet"
            if df is None or len(df) == 0:
                pd.DataFrame({"info": ["No data for this filter"]}).to_excel(
                    writer, sheet_name=name, index=False
                )
                continue

            write_index = df.index.name is not None  # the price grid uses check_in as index
            df.to_excel(writer, sheet_name=name, index=write_index)
            ws = writer.sheets[name]
            offset = 1 if write_index else 0
            n_rows = df.shape[0]
            n_cols = df.shape[1] + offset

            # Re-write the header row with formatting.
            if write_index:
                ws.write(0, 0, df.index.name, header_fmt)
            for c, col in enumerate(df.columns):
                ws.write(0, c + offset, str(col), header_fmt)

            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, n_rows, n_cols - 1)

            # Index column width.
            if write_index:
                idx_w = max([len(str(df.index.name or ""))] + [len(str(v)) for v in df.index]) + 2
                ws.set_column(0, 0, min(idx_w, 40))

            # Data columns: width + money format where appropriate.
            for c, col in enumerate(df.columns):
                series = df[col]
                width = max([len(str(col))] + [len(str(v)) for v in series.head(300)]) + 2
                is_money = (
                    pd.api.types.is_numeric_dtype(series)
                    and str(col).lower() not in _NON_MONEY_NUMERIC
                )
                ws.set_column(c + offset, c + offset, min(width, 40), money_fmt if is_money else None)

    return buffer.getvalue()


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
tab1, tab3, tab4, tab5 = st.tabs([
    "📊 Pricing Dashboard",
    "📥 Competitor Price Upload",
    "📈 Rate Shopping",
    "⚙️ Settings",
])

# ==================== TAB 1: PRICING DASHBOARD ====================
with tab1:
    st.header("Generate Pricing Recommendations")

    # Load defaults from config (local)
    cfg_obj = AppConfig()
    currency = cfg_obj.currency
    default_horizon = int(cfg_obj.horizon_days)
    default_occupancy = int(cfg_obj.occupancy)

    st.subheader("📅 Select Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today(),
            min_value=date.today(),
            help="Select the start date for pricing analysis",
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today() + timedelta(days=default_horizon),
            min_value=date.today(),
            help="Select the end date for pricing analysis",
        )

    st.subheader("🛏️ Room Configuration")
    col3, col4 = st.columns(2)
    with col3:
        occupancy = st.selectbox(
            "Room Type / Occupancy",
            options=[1, 2, 3, 4],
            index=[1, 2, 3, 4].index(default_occupancy) if default_occupancy in [1, 2, 3, 4] else 1,
            help="Select the number of guests per room",
            format_func=lambda x: {
                1: "Single (1 guest)",
                2: "Double (2 guests)",
                3: "Triple (3 guests)",
                4: "Family (4 guests)",
            }.get(x, f"{x} guests"),
        )
    with col4:
        dry_run = st.checkbox(
            "DRY_RUN (do not push live)",
            value=os.getenv("DRY_RUN", "true").lower() == "true",
            help="When enabled, rates are not pushed to the booking system.",
        )

    st.divider()

    if st.button("🔄 Generate Pricing Recommendations", type="primary", use_container_width=True):
        if start_date >= end_date:
            st.error("⚠️ End date must be after start date!")
        else:
            with st.spinner("Running pricing locally..."):
                try:
                    run_id = create_run(
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        dry_run=bool(dry_run),
                        occupancy=int(occupancy),
                    )

                    recs = run_pricing(
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        occupancy=int(occupancy),
                    )
                    save_recommendations(run_id, recs)

                    df = pd.DataFrame(get_recommendations(run_id))
                    if df.empty:
                        st.warning("No recommendations returned.")
                    else:
                        df["date"] = pd.to_datetime(df["date"]).dt.date
                        df = df.sort_values("date")

                        st.success("✅ Recommendations generated successfully!")

                        col_m1, col_m2, col_m3 = st.columns(3)
                        with col_m1:
                            st.metric("Total Days", len(df))
                        with col_m2:
                            st.metric("Avg. Recommended Rate", f"{currency}{df['recommended_rate'].mean():.2f}")
                        with col_m3:
                            st.metric("Avg. Lowest Competitor", f"{currency}{df['lowest_competitor'].mean():.2f}")

                        st.subheader("📋 Detailed Recommendations")
                        display_df = df.copy()
                        display_df["date"] = display_df["date"].astype(str)
                        display_df["recommended_rate"] = display_df["recommended_rate"].apply(lambda x: f"{currency}{x:.2f}")
                        display_df["lowest_competitor"] = display_df["lowest_competitor"].apply(lambda x: f"{currency}{x:.2f}")

                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            column_config={
                                "date": "Date",
                                "recommended_rate": "Recommended Rate",
                                "lowest_competitor": "Lowest Competitor",
                            },
                            hide_index=True,
                        )

                        st.divider()
                        st.subheader("📤 Push to Simple Booking")
                        if dry_run:
                            st.info("🔒 DRY_RUN enabled: pushing is disabled.")
                        else:
                            st.info("Push is only available via the FastAPI backend deployment.")

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ==================== TAB 3: COMPETITOR PRICE UPLOAD ====================
with tab3:
    st.header("Upload competitor pricing table")
    st.markdown(
        "Upload a spreadsheet with **one row per day**. The first column must be `date`. "
        "All other columns should be competitor prices. You can either:\n"
        "- Use columns like `COMP_A`, `COMP_B` (single room category), or\n"
        "- Use columns like `double__COMP_A`, `double__COMP_B`, `triple__COMP_A` (multiple room categories).\n\n"
        "Supported formats: CSV, XLSX, ODS."
    )

    # Keep track of which file was last loaded so we can avoid stale session state
    if "uploaded_competitor_file_name" not in st.session_state:
        st.session_state["uploaded_competitor_file_name"] = None

    def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _maybe_promote_first_row_as_header(df: pd.DataFrame) -> pd.DataFrame:
        """If the sheet looks like it has a header row inside the data (common in ODS exports), promote it."""
        if df.empty:
            return df

        first_row = df.iloc[0]
        if any(str(c).lower().startswith("unnamed") for c in df.columns) and any(
            isinstance(v, str) and v.strip() for v in first_row.values
        ):
            new_cols = [str(v).strip() if str(v).strip() else str(old) for old, v in zip(df.columns, first_row.values)]
            df2 = df.iloc[1:].copy()
            df2.columns = new_cols
            return df2

        return df

    def _find_date_col(df: pd.DataFrame) -> str | None:
        for c in df.columns:
            if str(c).strip().lower() == "date":
                return c

        for c in df.columns:
            if str(c).lower().startswith("unnamed"):
                try:
                    v = df[c].iloc[0]
                except Exception:
                    continue
                if isinstance(v, str) and v.strip().lower() == "date":
                    return c

        return None

    def _coerce_date_column(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
        return df.dropna(subset=[date_col])

    def _looks_like_two_level_header_competitor_layout(df: pd.DataFrame) -> bool:
        """Heuristic for the provided ODS: columns like capobianco/capobianco.1 and first row like singola/doppia."""
        if df.empty or df.shape[1] < 3:
            return False

        # Ignore first column (often date/unnamed)
        rest = list(df.columns[1:])
        has_dot_dupes = any(str(c).endswith(".1") or str(c).endswith(".2") for c in rest)

        try:
            row0 = df.iloc[0, 1:]
        except Exception:
            return False

        row0_vals = [str(v).strip().lower() if v is not None else "" for v in row0.values]
        room_tokens = {"singola", "doppia", "tripla", "quadrupla", "single", "double", "triple", "family"}
        has_room_tokens = any(v in room_tokens for v in row0_vals)

        return bool(has_dot_dupes and has_room_tokens)

    def _apply_two_level_header_competitor_layout(df_raw: pd.DataFrame) -> pd.DataFrame:
        """Convert layout: columns are competitor names (with .1 duplicates), first data row is room type.

        Output columns: date + {room}__{competitor}
        """
        if df_raw.empty:
            return df_raw

        df = df_raw.copy()

        # Determine date column candidate (usually first column)
        date_col = df.columns[0]

        # Room labels are in first row (excluding date col)
        room_labels = [str(v).strip().lower() for v in df.iloc[0, 1:].values]

        # Competitor column names as read (excluding date col)
        comp_cols = list(df.columns[1:])

        def _base_competitor_name(col: str) -> str:
            s = str(col).strip()
            # Pandas duplicate columns become name, name.1, name.2...
            if "." in s and s.rsplit(".", 1)[-1].isdigit():
                return s.rsplit(".", 1)[0]
            return s

        new_names = {}
        for i, c in enumerate(comp_cols):
            comp = _base_competitor_name(c)
            room = room_labels[i] if i < len(room_labels) else "default"
            if not room:
                room = "default"
            new_names[c] = f"{room}__{comp}"

        # Drop the header-in-data row and rename columns
        df2 = df.iloc[1:].copy()
        df2 = df2.rename(columns=new_names)
        # Keep date column name stable
        df2 = df2.rename(columns={date_col: "date"})
        return df2

    def _ensure_literal_date_column(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure the dataframe contains a literal 'date' column (lowercase).

        Streamlit users frequently upload sheets where the date header is 'Date', 'DATE', or has spaces.
        The rest of the UI expects a stable column name.
        """
        df2 = df.copy()
        cols = list(df2.columns)
        # If already has date (any casing)
        for c in cols:
            if str(c).strip().lower() == "date":
                if c != "date":
                    df2 = df2.rename(columns={c: "date"})
                return df2
        return df2

    def _ensure_date_column_from_any(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure there is a usable 'date' column.

        Prefers:
        1) an existing date-like column (case-insensitive match)
        2) the user's last selection stored in session
        3) a detected date column via _find_date_col
        4) the first column
        """
        df2 = df.copy()

        # 1) already has a date column in any casing
        df2 = _ensure_literal_date_column(df2)
        if "date" in [str(c).strip().lower() for c in df2.columns]:
            return df2

        # 2) user's last selection
        preferred = st.session_state.get("competitor_date_col_value")
        if preferred and preferred in df2.columns:
            df2 = _coerce_date_column(df2, preferred)
            if preferred != "date":
                df2 = df2.rename(columns={preferred: "date"})
            df2 = _ensure_literal_date_column(df2)
            return df2

        # 3) detected
        detected = _find_date_col(df2)
        if detected and detected in df2.columns:
            df2 = _coerce_date_column(df2, detected)
            if detected != "date":
                df2 = df2.rename(columns={detected: "date"})
            df2 = _ensure_literal_date_column(df2)
            return df2

        # 4) fallback to first column
        if len(df2.columns) > 0:
            first = df2.columns[0]
            df2 = _coerce_date_column(df2, first)
            if first != "date":
                df2 = df2.rename(columns={first: "date"})
            df2 = _ensure_literal_date_column(df2)

        return df2

    def _load_table(df_raw: pd.DataFrame, *, source_name: str | None = None):
        df_raw = _normalize_cols(df_raw)

        # Special-case: provided ODS uses competitor columns + room labels in first data row
        if _looks_like_two_level_header_competitor_layout(df_raw):
            df_raw = _apply_two_level_header_competitor_layout(df_raw)

        # Try to fix common ODS layout where row 1 contains labels (Date / singola / doppia)
        df_raw = _maybe_promote_first_row_as_header(df_raw)
        df_raw = _normalize_cols(df_raw)

        detected = _find_date_col(df_raw)

        # Persist the user's choice per-source to survive reruns
        default_choice = st.session_state.get("competitor_date_col_value")
        options = list(df_raw.columns)
        if default_choice in options:
            default_index = options.index(default_choice)
        elif detected in options:
            default_index = options.index(detected)
        else:
            default_index = 0

        chosen = st.selectbox(
            "Select date column",
            options=options,
            index=default_index,
            help="Pick the column that contains dates.",
            key="competitor_date_col",
        )
        st.session_state["competitor_date_col_value"] = chosen

        df_final = _coerce_date_column(df_raw, chosen)
        if df_final.empty:
            st.error("No valid date rows found. Check date formatting.")
            return

        # Normalize date column name to literal 'date' so the rest of the pipeline is stable.
        original_date_col = chosen
        if original_date_col != "date":
            df_final = df_final.rename(columns={original_date_col: "date"})

        df_final = _ensure_literal_date_column(df_final)

        st.session_state["uploaded_competitor_prices"] = df_final
        st.session_state["uploaded_competitor_original_date_col"] = original_date_col
        st.session_state["uploaded_competitor_file_name"] = source_name

        st.success(f"Loaded {len(df_final)} rows")
        st.dataframe(df_final.head(50), use_container_width=True)

    # Convenience: load the bundled file if present
    default_ods_path = REPO_ROOT / "competitor" / "Competitors.ods"
    if default_ods_path.exists():
        if st.button("Load bundled competitor/Competitors.ods", use_container_width=True):
            try:
                df_raw = pd.read_excel(default_ods_path, engine="odf")
                _load_table(df_raw)
            except Exception as e:
                st.error(
                    "Failed to read ODS. Ensure dependency 'odfpy' is installed (required for .ods). "
                    f"Details: {e}"
                )

    uploaded = st.file_uploader(
        "Upload file",
        type=["csv", "xlsx", "ods"],
        help="Date format: YYYY-MM-DD (or Excel date).",
    )

    # If a new file is uploaded, clear previous parsed table to avoid stale state
    if uploaded is not None and st.session_state.get("uploaded_competitor_file_name") != uploaded.name:
        st.session_state.pop("uploaded_competitor_prices", None)
        st.session_state.pop("uploaded_competitor_original_date_col", None)

    if uploaded is not None:
        try:
            name = uploaded.name.lower()
            if name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            elif name.endswith(".ods"):
                df_raw = pd.read_excel(uploaded, engine="odf")
            else:
                df_raw = pd.read_excel(uploaded)

            # Always attempt to load/normalize on reruns too
            _load_table(df_raw, source_name=uploaded.name)

        except Exception as e:
            st.error(
                "Failed to parse upload. For ODS files on Streamlit Cloud, you must add 'odfpy' to requirements. "
                f"Details: {e}"
            )

    df_uploaded = st.session_state.get("uploaded_competitor_prices")
    if df_uploaded is None:
        st.info("Upload a file to compute daily lowest/avg/highest competitor prices.")
    else:
        # Be defensive: ensure a usable 'date' column even if the stored df came from an older run
        df_uploaded = _ensure_date_column_from_any(df_uploaded)
        st.session_state["uploaded_competitor_prices"] = df_uploaded

        if "date" not in [str(c).strip().lower() for c in df_uploaded.columns]:
            st.error(
                "Missing required column: date. "
                "Please re-upload and select the correct date column in the dropdown."
            )
            with st.expander("Debug: show detected columns"):
                st.write(list(df_uploaded.columns))
                st.write(df_uploaded.head(10))
            st.stop()

        # Use the normalized literal 'date' column
        date_col = next(c for c in df_uploaded.columns if str(c).strip().lower() == "date")
        value_cols = [c for c in df_uploaded.columns if c != date_col]

        # Detect room categories by `room__competitor` pattern
        room_cols = {}
        for col in value_cols:
            if "__" in col:
                room, comp = col.split("__", 1)
                room = room.strip().lower()
                comp = comp.strip()
                room_cols.setdefault(room, []).append(col)
            else:
                room_cols.setdefault("default", []).append(col)

        rooms = sorted(room_cols.keys())
        selected_room = st.selectbox("Room category", options=rooms, index=0)

        # Compute daily stats for selected room
        df_room = df_uploaded[[date_col] + room_cols[selected_room]].copy()

        # Coerce numeric
        for c in room_cols[selected_room]:
            df_room[c] = pd.to_numeric(df_room[c], errors="coerce")

        df_room["lowest"] = df_room[room_cols[selected_room]].min(axis=1, skipna=True)
        df_room["average"] = df_room[room_cols[selected_room]].mean(axis=1, skipna=True)
        df_room["highest"] = df_room[room_cols[selected_room]].max(axis=1, skipna=True)

        df_stats = df_room[[date_col, "lowest", "average", "highest"]].sort_values(date_col)

        st.subheader("Daily summary")
        st.dataframe(df_stats, use_container_width=True, hide_index=True)

        st.subheader("Summary metrics")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Avg lowest", f"{df_stats['lowest'].mean():.2f}" if df_stats["lowest"].notna().any() else "-")
        with c2:
            st.metric("Avg average", f"{df_stats['average'].mean():.2f}" if df_stats["average"].notna().any() else "-")
        with c3:
            st.metric("Avg highest", f"{df_stats['highest'].mean():.2f}" if df_stats["highest"].notna().any() else "-")

        # Optional download
        csv_bytes = df_stats.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download daily summary (CSV)",
            data=csv_bytes,
            file_name=f"competitor_summary_{selected_room}.csv",
            mime="text/csv",
            use_container_width=True,
        )

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
        # ---------------- Competitor hotels ----------------
        st.subheader("Step 1 — 🏨 Competitor hotels")
        st.caption("Your tracked hotels. Add Elbitat (mark it *self*) plus 5–15 competitors. A Booking.com URL gives the most precise scrape.")

        with st.expander("➕ Add hotel"):
            with st.form("rs_add_hotel", clear_on_submit=True):
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
                            rss.add_competitor_hotel(
                                name=h_name, booking_url=h_url or None, location=h_loc or None,
                                active=bool(h_active), is_self=bool(h_self), notes=h_notes or None,
                            )
                            st.success(f"Added {h_name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        try:
            hotels = rss.list_competitor_hotels()
        except Exception as e:
            hotels = []
            st.error(f"Could not load hotels: {e}")

        if not hotels:
            st.info("No hotels yet. Add Elbitat (as *self*) and a few competitors above.")
        else:
            for h in hotels:
                c1, c2, c3 = st.columns([5, 2, 1])
                with c1:
                    tag = "⭐ SELF" if h["is_self"] else ("🟢" if h["active"] else "🔴")
                    st.markdown(f"**{tag} {h['name']}**" + (f" — [link]({h['booking_url']})" if h.get("booking_url") else ""))
                    if h.get("location"):
                        st.caption(h["location"])
                with c2:
                    if st.button("Toggle active", key=f"rs_toggle_{h['id']}"):
                        rss.update_competitor_hotel(h["id"], {"active": not h["active"]})
                        st.rerun()
                with c3:
                    if st.button("🗑️", key=f"rs_del_{h['id']}"):
                        rss.delete_competitor_hotel(h["id"])
                        st.rerun()

        st.divider()

        # ---------------- Run a price check ----------------
        st.subheader("Step 2 — ▶️ Fetch prices (runs Apify)")
        st.caption(
            "Pick which **future check-in dates** to collect prices for, then click the button. "
            "This calls Apify and can take a couple of minutes. Use this when you want fresh data."
        )
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            rs_start = st.date_input("From check-in", value=date.today() + timedelta(days=14), key="rs_start")
        with rc2:
            rs_end = st.date_input("To check-in", value=date.today() + timedelta(days=20), key="rs_end")
        with rc3:
            rs_nights = st.selectbox("Nights", options=[1, 2, 3, 7], index=0, key="rs_nights")
        rc4, rc5 = st.columns(2)
        with rc4:
            rs_adults = st.selectbox("Adults", options=[1, 2, 3, 4], index=1, key="rs_adults")
        with rc5:
            rs_children = st.number_input("Children", min_value=0, max_value=6, value=0, key="rs_children")

        st.caption(
            f"Cost guards: ≤{rss.MAX_DATES_PER_MANUAL_RUN} dates per run, ≤{rss.MAX_COMPETITORS} competitors, "
            f"≤{rss.MAX_HORIZON_DAYS}-day horizon, duplicate searches within "
            f"{rss.DEDUP_WINDOW_HOURS}h are skipped. One Apify run per check-in date."
        )

        if st.button("🔄 Run price check", type="primary", use_container_width=True):
            if rs_start > rs_end:
                st.error("'From' must be on or before 'To'.")
            else:
                with st.spinner("Starting Apify runs and waiting briefly for results…"):
                    try:
                        # Brief wait catches fast runs inline; Apify queues the rest, which the
                        # user pulls with the Sync button (avoids the page hanging for minutes).
                        results = rss.run_price_check(
                            start_date=rs_start, end_date=rs_end, nights=int(rs_nights),
                            adults=int(rs_adults), children=int(rs_children),
                            wait=True, poll_timeout_secs=90,
                        )
                        ok = sum(1 for r in results if r.get("status") == "succeeded")
                        running = sum(1 for r in results if r.get("status") == "running")
                        skipped = sum(1 for r in results if r.get("status") == "skipped")
                        failed = sum(1 for r in results if r.get("status") == "failed")
                        st.success(f"✅ Loaded {ok}/{len(results)} dates. Results below show these dates.")
                        if running:
                            st.info(
                                f"⏳ {running} date(s) still running on Apify (it queues runs). "
                                "Click **🔁 Sync latest runs** below in a minute to load them — click again if needed."
                            )
                        if skipped:
                            st.caption(f"{skipped} date(s) skipped — already scraped in the last {rss.DEDUP_WINDOW_HOURS}h.")
                        if failed:
                            st.warning(f"{failed} date(s) failed to start.")
                            st.dataframe(pd.DataFrame([r for r in results if r.get("status") == "failed"]),
                                         use_container_width=True, hide_index=True)
                        # Point the results view at the dates we just scraped.
                        st.session_state["rs_in_start"] = rs_start
                        st.session_state["rs_in_end"] = rs_end
                        st.session_state["rs_in_nights"] = int(rs_nights)
                    except Exception as e:
                        st.error(f"Error: {e}")

        st.caption("After starting a check, wait ~1–2 min then click this to load the results (no new scraping cost):")
        if st.button("🔁 Sync latest runs (no new scraping)", type="primary", use_container_width=True):
            with st.spinner("Checking Apify for finished runs…"):
                try:
                    synced = rss.sync_pending_runs()
                    if synced:
                        done = sum(1 for s in synced if s.get("status") == "succeeded")
                        still = sum(1 for s in synced if s.get("status") == "running")
                        st.success(f"Checked {len(synced)} run(s): {done} loaded with data, {still} still running.")
                        if still:
                            st.caption("Some are still running on Apify — click Sync again in a minute.")
                        st.dataframe(pd.DataFrame(synced), use_container_width=True, hide_index=True)
                    else:
                        st.info("No pending runs — everything is already synced.")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()

        # ---------------- Insights table ----------------
        st.subheader("Step 3 — 📊 Results: Elbitat vs competitors")
        st.caption(
            "Shows prices **already collected** (no Apify cost). After a scrape this jumps to the "
            "dates you just fetched; widen the range to review everything you've gathered over time."
        )
        # Initialise once so the run button can auto-jump these without the
        # "value set via Session State API" warning (no value=/index= below).
        st.session_state.setdefault("rs_in_start", date.today())
        st.session_state.setdefault("rs_in_end", date.today() + timedelta(days=120))
        st.session_state.setdefault("rs_in_nights", "all")

        ic1, ic2, ic3, ic4 = st.columns(4)
        with ic1:
            in_start = st.date_input("From", key="rs_in_start")
        with ic2:
            in_end = st.date_input("To", key="rs_in_end")
        with ic3:
            in_nights = st.selectbox("Stay length", options=["all", 1, 2, 3, 7], key="rs_in_nights")
        with ic4:
            price_basis = st.radio(
                "Price basis", options=["Per night", "Total stay"], index=0, key="rs_price_basis",
                help="Booking.com returns the TOTAL price for the stay. 'Per night' divides it by the number of nights.",
            )
        per_night = price_basis == "Per night"
        idf_export = None   # populated below; used by the Excel download
        grid_export = None

        try:
            insights = rss.get_insights(
                start_date=in_start, end_date=in_end,
                nights=None if in_nights == "all" else int(in_nights),
            )
        except Exception as e:
            insights = []
            st.error(f"Could not load insights: {e}")

        if not insights:
            st.info("No observations yet for this filter. Run a price check above.")
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
        try:
            matrix = rss.get_price_matrix(
                start_date=in_start, end_date=in_end,
                nights=None if in_nights == "all" else int(in_nights),
            )
        except Exception as e:
            matrix = []
            st.error(f"Could not load price grid: {e}")

        if not matrix:
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
                runs = rss.list_recent_runs(limit=15)
                if runs:
                    rdf = pd.DataFrame(runs)[
                        [c for c in ["id", "status", "item_count", "cost_usd", "started_at", "finished_at", "error_message"]
                         if c in pd.DataFrame(runs).columns]
                    ]
                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                else:
                    st.caption("No runs yet.")
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