"""
Handicap Calculator Module - Handles handicap calculations
"""
import pandas as pd
import streamlit as st
import os
import json

# ================================================================================
# LOAD COURSE DATA FROM JSON (YOUR STRUCTURE)
# ================================================================================
@st.cache_data
def load_course_data(uploaded_file=None):
    """
    Load course data from:
    1. Uploaded JSON file (optional)
    2. data/course_data.json (default)

    JSON structure expected:

    {
      "COURSE NAME": {
        "tees": {
          "TeeName": {
            "slope": 123,
            "rating": 71.2,
            "par": 72
          }
        }
      }
    }
    """

    try:
        # 1. Uploaded JSON
        if uploaded_file:
            data = json.load(uploaded_file)
            return _flatten_course_json(data)

        # 2. Load from /data folder
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        json_path = os.path.join(data_dir, "course_data.json")

        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _flatten_course_json(data)

        st.error("❌ course_data.json not found in /data folder.")
        return None

    except Exception as e:
        st.error(f"Error loading course data: {e}")
        return None


def _flatten_course_json(data):
    """
    Convert your nested JSON structure into a clean DataFrame.
    """

    rows = []

    for course_name, course_info in data.items():
        tees = course_info.get("tees", {})
        for tee_name, tee_info in tees.items():
            rows.append({
                "Course Name": course_name,
                "Tee Name": tee_name,
                "Slope Rating": tee_info.get("slope"),
                "Course Rating": tee_info.get("rating"),
                "Par": tee_info.get("par"),
            })

    df = pd.DataFrame(rows)
    df = df.fillna("")
    return df


# ================================================================================
# CALCULATE COURSE HANDICAP
# ================================================================================
def calculate_course_handicap(handicap_index, slope_rating, course_rating, par):
    """Calculate course handicap from index and course data"""
    try:
        index = float(handicap_index)
        slope = float(slope_rating)
        rating = float(course_rating)
        par_val = float(par)
        return index * (slope / 113.0) + (rating - par_val)
    except:
        return None


# ================================================================================
# COURSE SELECTOR
# ================================================================================
def render_course_tee_selector(course_df, key_prefix):
    """Render course and tee selectors"""
    if course_df is None:
        st.error("Course data not loaded.")
        return None, None, None

    col1, col2 = st.columns(2)

    with col1:
        course_names = sorted(course_df["Course Name"].unique().tolist())
        selected_course = st.selectbox("Select Course", course_names, key=f"{key_prefix}_course")

    with col2:
        tees = course_df[course_df["Course Name"] == selected_course]
        tee_names = sorted(tees["Tee Name"].tolist())
        selected_tee = st.selectbox("Select Tee", tee_names, key=f"{key_prefix}_tee")

    tee_data = tees[tees["Tee Name"] == selected_tee].iloc[0]

    st.info(
        f"Course: **{selected_course}** | Tee: **{selected_tee}** | "
        f"Slope: {tee_data['Slope Rating']} | Rating: {tee_data['Course Rating']} | Par: {int(tee_data['Par'])}"
    )

    return selected_course, selected_tee, tee_data
