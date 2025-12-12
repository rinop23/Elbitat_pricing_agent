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
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Pricing Dashboard",
    "🏢 Competitor Management",
    "📥 Competitor Price Upload",
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

# ==================== TAB 2: COMPETITOR MANAGEMENT ====================
with tab2:
    st.header("Manage Competitor Hotels")
    st.markdown("Add, edit, or remove competitor hotels to track their pricing.")

    with st.expander("➕ Add New Competitor", expanded=False):
        with st.form("add_competitor_form", clear_on_submit=True):
            new_name = st.text_input("Hotel Name*", placeholder="e.g., Grand Hotel Roma")
            new_website = st.text_input("Website URL", placeholder="e.g., https://www.grandhotelroma.com")
            new_active = st.checkbox("Active", value=True, help="Track this competitor's prices")

            submitted = st.form_submit_button("Add Competitor", type="primary", use_container_width=True)
            if submitted:
                if not new_name:
                    st.error("⚠️ Hotel name is required!")
                else:
                    try:
                        add_competitor(
                            name=new_name,
                            website=new_website if new_website else None,
                            active=bool(new_active),
                        )
                        st.success(f"✅ Added competitor: {new_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

    st.divider()
    st.subheader("📋 Current Competitors")

    try:
        competitors = list_competitors()
        if not competitors:
            st.info("ℹ️ No competitors added yet. Add your first competitor above!")
        else:
            for comp in competitors:
                with st.container():
                    col_info, col_actions = st.columns([4, 1])

                    with col_info:
                        status_icon = "🟢" if comp.get("active", True) else "🔴"
                        st.markdown(f"### {status_icon} {comp['name']}")
                        if comp.get("website"):
                            st.markdown(f"🔗 [{comp['website']}]({comp['website']})")
                        else:
                            st.markdown("🔗 *No website specified*")

                    with col_actions:
                        if st.button("🗑️ Delete", key=f"delete_{comp['id']}", use_container_width=True):
                            delete_competitor(int(comp["id"]))
                            st.rerun()

                    st.divider()

    except Exception as e:
        st.error(f"❌ Error loading competitors: {str(e)}")

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

    # Convenience: load the bundled file if present
    default_ods_path = REPO_ROOT / "competitor" / "Competitors.ods"
    if default_ods_path.exists():
        if st.button("Load bundled competitor/Competitors.ods", use_container_width=True):
            try:
                df_raw = pd.read_excel(default_ods_path, engine="odf")
                df_raw.columns = [str(c).strip() for c in df_raw.columns]
                st.session_state["uploaded_competitor_prices"] = df_raw
                st.success(f"Loaded bundled file: {default_ods_path.name}")
            except Exception as e:
                st.error(
                    "Failed to read ODS. Ensure dependency 'odfpy' is installed (required for .ods). "
                    f"Details: {e}"
                )

    uploaded = st.file_uploader(
        "Upload file",
        type=["csv", "xlsx", "ods"],
        help="Date format: YYYY-MM-DD.",
    )

    if uploaded is not None:
        try:
            name = uploaded.name.lower()
            if name.endswith(".csv"):
                df_raw = pd.read_csv(uploaded)
            elif name.endswith(".ods"):
                df_raw = pd.read_excel(uploaded, engine="odf")
            else:
                df_raw = pd.read_excel(uploaded)

            # Normalize columns
            df_raw.columns = [str(c).strip() for c in df_raw.columns]
            if "date" not in [c.lower() for c in df_raw.columns]:
                st.error("Missing required column: date")
                st.stop()

            # Find the actual date column name (case-insensitive)
            date_col = next(c for c in df_raw.columns if c.lower() == "date")
            df_raw[date_col] = pd.to_datetime(df_raw[date_col], errors="coerce").dt.date
            df_raw = df_raw.dropna(subset=[date_col])

            # Keep a copy in session
            st.session_state["uploaded_competitor_prices"] = df_raw

            st.success(f"Loaded {len(df_raw)} rows")
            st.dataframe(df_raw.head(50), use_container_width=True)

        except Exception as e:
            st.error(
                "Failed to parse upload. For ODS files on Streamlit Cloud, you must add 'odfpy' to requirements. "
                f"Details: {e}"
            )

    df_uploaded = st.session_state.get("uploaded_competitor_prices")
    if df_uploaded is None:
        st.info("Upload a file to compute daily lowest/avg/highest competitor prices.")
    else:
        date_col = next(c for c in df_uploaded.columns if c.lower() == "date")
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

# ==================== TAB 4: SETTINGS ====================
with tab4:
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