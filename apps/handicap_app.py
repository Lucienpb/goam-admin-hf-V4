#-------------------------------------------------
# Handicap Scraper App (Mode-based version)
#   - Single Player Lookup
#   - Batch Processing  (Excel upload + download)
#   - Handicap Calculator (manual input)
#-------------------------------------------------

import streamlit as st
import pandas as pd
import io
from datetime import datetime

from utils.handicap_api import fetch_handicap
from utils.handicap_calculator import (
    render_course_tee_selector,
    calculate_course_handicap,
)

# ---------------- SAFE ROUND FIX ----------------
def safe_round(value):
    if value is None:
        return None
    try:
        return int(round(value))
    except Exception:
        return None
# -------------------------------------------------


# ============================================================
# SESSION LOGIN STATE
# ============================================================
if "hcp_logged_in" not in st.session_state:
    st.session_state["hcp_logged_in"] = False
    st.session_state["hcp_username"] = None
    st.session_state["hcp_password"] = None


# ============================================================
# MAIN ENTRY POINT (called from app.py)
# ============================================================
def run(mode, credentials_unused, course_df):

    if mode == "single":
        show_single_player(course_df)

    elif mode == "batch":
        show_batch_processing(course_df)

    elif mode == "calculator":
        show_handicap_calculator(course_df)


# ============================================================
# LOGIN BLOCK (shared by single + batch)
# ============================================================
def ensure_hcp_login(key_prefix="single"):
    """
    Shows login UI only if not logged in.
    Returns (username, password) if logged in, else None.
    """

    if not st.session_state["hcp_logged_in"]:
        st.subheader("🔐 Login to Handicaps.co.za")

        username = st.text_input("HNA Username", key=f"{key_prefix}_user")
        password = st.text_input("HNA Password", type="password", key=f"{key_prefix}_pass")

        if st.button("Login", key=f"{key_prefix}_login_btn"):
            if not username or not password:
                st.error("Please enter both username and password.")
                return None

            # Test login with harmless dummy member
            try:
                fetch_handicap(username, password, "000000")
                st.session_state["hcp_logged_in"] = True
                st.session_state["hcp_username"] = username
                st.session_state["hcp_password"] = password
                st.success("Logged in successfully!")
            except Exception:
                st.error("Login failed. Please check your credentials.")
                return None

    # Already logged in
    return (
        st.session_state["hcp_username"],
        st.session_state["hcp_password"],
    )


# ============================================================
# SINGLE PLAYER SCRAPER
# ============================================================
def show_single_player(course_df):
    st.header("🏌️ Single Player Lookup")

    # Login first
    creds = ensure_hcp_login("single")
    if not creds:
        return

    username, password = creds

    course, tee, tee_data = render_course_tee_selector(course_df, "single")

    member = st.text_input("HNA Membership No.", key="single_member")

    if st.button("Search Player"):
        if not member.strip():
            st.error("Please enter a membership number.")
            return

        with st.spinner("Fetching from Handicap API..."):
            try:
                name, index = fetch_handicap(
                    username,
                    password,
                    member,
                )
            except Exception as e:
                st.error(f"Error calling Handicap API: {e}")
                return

        if not name:
            st.error("Player not found.")
        else:
            st.success("Player found!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Membership", member)
            col2.metric("Name", name)
            col3.metric("Handicap Index", index if index else "Pending")

            if tee_data is not None and index:
                course_hcp = calculate_course_handicap(
                    index,
                    tee_data["Slope Rating"],
                    tee_data["Course Rating"],
                    tee_data["Par"],
                )
                hcp_display = safe_round(course_hcp)
                st.metric(
                    "Course Handicap",
                    hcp_display if hcp_display is not None else "N/A",
                )


# ============================================================
# BATCH PROCESSING
# ============================================================
def show_batch_processing(course_df):
    st.header("📦 Batch Processing")

    # Login first
    creds = ensure_hcp_login("batch")
    if not creds:
        return

    username, password = creds

    course, tee, tee_data = render_course_tee_selector(course_df, "batch")

    uploaded = st.file_uploader("Upload player_ids.xlsx", type=["xlsx"])

    if uploaded and st.button("Process All"):
        df_input = pd.read_excel(uploaded)

        membership_col = next(
            (c for c in df_input.columns if "member" in c.lower()), None
        )
        cap_col = next(
            (c for c in df_input.columns if "cap" in c.lower()), None
        )
        name_col = next(
            (c for c in df_input.columns if "name" in c.lower()), None
        )

        if not membership_col or not cap_col:
            st.error(
                "Excel must contain at least 'membership' and 'cap' columns "
                "(case-insensitive match)."
            )
            return

        members = (
            df_input[membership_col]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )
        caps = df_input[cap_col]
        names = df_input[name_col] if name_col else [None] * len(members)

        results = []
        progress = st.progress(0)
        status_text = st.empty()

        for i, (mem, cap, fallback) in enumerate(zip(members, caps, names)):
            mem = str(mem).strip()
            status_text.write(f"Searching member: {mem}")

            try:
                name, scraped_index = fetch_handicap(
                    username,
                    password,
                    mem,
                    fallback_name=fallback,
                )
            except Exception:
                name, scraped_index = fallback, None

            # Decide final index (cap vs scraped)
            final_index = None
            if scraped_index:
                try:
                    scraped_f = float(scraped_index)
                    final_index = cap if scraped_f > cap else scraped_f
                except Exception:
                    final_index = cap
            else:
                final_index = cap

            # Course handicap if tee_data is available
            course_hcp_val = None
            if tee_data is not None and final_index is not None:
                course_hcp_val = safe_round(
                    calculate_course_handicap(
                        final_index,
                        tee_data["Slope Rating"],
                        tee_data["Course Rating"],
                        tee_data["Par"],
                    )
                )

            results.append(
                {
                    "membership": mem,
                    "name": name,
                    "handicap_index_scraped": scraped_index,
                    "cap": cap,
                    "final_index": final_index,
                    "course_handicap": course_hcp_val,
                }
            )

            progress.progress((i + 1) / len(members))

        status_text.write("Done")

        df_out = pd.DataFrame(results)

        output = io.BytesIO()
        df_out.to_excel(output, index=False)
        output.seek(0)

        st.download_button(
            "Download Results",
            data=output.getvalue(),
            file_name=f"GOAM_HI_{datetime.now().strftime('%Y%m')}_PW.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.dataframe(df_out)


# ============================================================
# HANDICAP CALCULATOR
# ============================================================
def show_handicap_calculator(course_df):
    st.header("🧮 Handicap Calculator")

    index = st.number_input(
        "Handicap Index", min_value=0.0, max_value=54.0, step=0.1
    )

    course, tee, tee_data = render_course_tee_selector(course_df, "calc")

    if tee_data is not None:
        hcp = calculate_course_handicap(
            index,
            tee_data["Slope Rating"],
            tee_data["Course Rating"],
            tee_data["Par"],
        )
        hcp_display = safe_round(hcp)
        st.metric(
            "Course Handicap",
            hcp_display if hcp_display is not None else "N/A",
        )
