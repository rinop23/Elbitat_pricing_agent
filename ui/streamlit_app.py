import os
import pandas as pd
import streamlit as st
import requests
from datetime import date, timedelta

# Page configuration
st.set_page_config(
    page_title="Hotel Pricing Agent",
    layout="wide",
    initial_sidebar_state="expanded"
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

# API base URL (adjust if backend runs on different port)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def _api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def _get_json(path: str, *, params=None):
    r = requests.get(_api_url(path), params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _post_json(path: str, *, payload=None):
    r = requests.post(_api_url(path), json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def _delete(path: str):
    r = requests.delete(_api_url(path), timeout=60)
    r.raise_for_status()
    return r.json() if r.content else {"ok": True}


# Main title
st.title("🏨 Hotel Pricing Agent")

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["📊 Pricing Dashboard", "🏢 Competitor Management", "⚙️ Settings"])

# ==================== TAB 1: PRICING DASHBOARD ====================
with tab1:
    st.header("Generate Pricing Recommendations")

    # Fetch defaults from backend (best-effort). Fall back to safe defaults.
    try:
        cfg = _get_json("/config")
    except Exception:
        cfg = {
            "hotel": {"currency": os.getenv("CURRENCY", "EUR")},
            "run": {"horizon_days": 120, "occupancy": 2},
            "pricing": {"min_rate": 0, "max_rate": 0, "weekend_uplift": 0, "undercut": 0, "max_change_pct": 0.1},
        }

    currency = (cfg.get("hotel") or {}).get("currency", os.getenv("CURRENCY", "EUR"))
    default_horizon = int((cfg.get("run") or {}).get("horizon_days", 120))
    default_occupancy = int((cfg.get("run") or {}).get("occupancy", 2))

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
            format_func=lambda x: {1: "Single (1 guest)", 2: "Double (2 guests)", 3: "Triple (3 guests)", 4: "Family (4 guests)"}.get(x, f"{x} guests"),
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
            with st.spinner("Running pricing in backend..."):
                try:
                    run = _post_json(
                        "/runs",
                        payload={
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat(),
                            "dry_run": bool(dry_run),
                            "occupancy": int(occupancy),
                        },
                    )
                    run_id = run["id"]
                    recs = _get_json(f"/recommendations/{run_id}")

                    df = pd.DataFrame(recs)
                    if df.empty:
                        st.warning("No recommendations returned.")
                    else:
                        # Format for display
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
                            if st.button("Push recommended rates", type="secondary", use_container_width=True):
                                resp = _post_json(
                                    f"/runs/{run_id}/push",
                                    payload={"currency": currency},
                                )
                                st.success(f"✅ Push complete: {resp}")

                except requests.HTTPError as e:
                    st.error(f"❌ Backend error: {e.response.text if e.response is not None else str(e)}")
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
                        _post_json(
                            "/competitors",
                            payload={
                                "name": new_name,
                                "website": new_website if new_website else None,
                                "active": bool(new_active),
                            },
                        )
                        st.success(f"✅ Added competitor: {new_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

    st.divider()
    st.subheader("📋 Current Competitors")

    try:
        competitors = _get_json("/competitors")
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
                            _delete(f"/competitors/{comp['id']}")
                            st.rerun()

                    st.divider()

    except Exception as e:
        st.error(f"❌ Error connecting to API: {str(e)}")
        st.info("💡 Make sure the backend API is running at " + API_BASE_URL)

# ==================== TAB 3: SETTINGS ====================
with tab3:
    st.header("Configuration Settings")
    st.markdown("Configure your hotel pricing parameters and system settings.")

    try:
        cfg = _get_json("/config")
    except Exception as e:
        st.error(f"Failed to load config from backend: {str(e)}")
        cfg = None

    if cfg:
        hotel = cfg.get("hotel") or {}
        run_cfg = cfg.get("run") or {}
        pricing = cfg.get("pricing") or {}

        col_set1, col_set2 = st.columns(2)

        with col_set1:
            st.subheader("🏨 Hotel Information")
            st.text_input("Currency", value=str(hotel.get("currency", "EUR")), disabled=True)
            st.text_input("Property ID", value=str(hotel.get("property_id", "")), disabled=True)
            st.text_input("Rate Plan ID", value=str(hotel.get("rate_plan_id", "")), disabled=True)

            st.subheader("💰 Pricing Limits")
            st.number_input("Minimum Rate", value=float(pricing.get("min_rate", 0.0)), disabled=True)
            st.number_input("Maximum Rate", value=float(pricing.get("max_rate", 0.0)), disabled=True)
            st.number_input("Max Change per Run (%)", value=float(pricing.get("max_change_pct", 0.1)) * 100.0, disabled=True)

        with col_set2:
            st.subheader("📊 Default Parameters")
            st.number_input("Default Horizon (days)", value=int(run_cfg.get("horizon_days", 120)), disabled=True)
            st.number_input("Default Occupancy", value=int(run_cfg.get("occupancy", 2)), disabled=True)
            st.number_input("Default Weekend Uplift", value=float(pricing.get("weekend_uplift", 0.0)), disabled=True)
            st.number_input("Default Market Position", value=float(pricing.get("undercut", 0.0)), disabled=True)

        st.divider()
        st.info("💡 To modify these settings, edit the `config/settings.yaml` file.")

# Footer
st.divider()
st.markdown("---")
st.markdown("🏨 **Hotel Pricing Agent** | Powered by AI & Market Intelligence")