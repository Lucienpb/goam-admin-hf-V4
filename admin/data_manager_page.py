#######################################
# Data Manager Page (Admin Only)
#######################################

import streamlit as st
import pandas as pd
from datetime import datetime
import json

from utils.github_storage import github_load_json, github_save_json

# -------------------------------------------------------------------
# SAFE HELPERS
# -------------------------------------------------------------------
def safe_str(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def safe_float(value, default=0.0):
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


# -------------------------------------------------------------------
# COURSES SECTION
# -------------------------------------------------------------------
def convert_course_excel_to_json(df: pd.DataFrame):
    required_cols = ["Course Name", "Tee Name", "Slope Rating", "Course Rating", "Par"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Course_Information.xlsx: {missing}")

    courses = {}

    for _, row in df.iterrows():
        course = safe_str(row.get("Course Name"))
        tee = safe_str(row.get("Tee Name"))

        if not course or not tee:
            continue

        slope = safe_float(row.get("Slope Rating"))
        rating = safe_float(row.get("Course Rating"))
        par = safe_int(row.get("Par"))

        if course not in courses:
            courses[course] = {"tees": {}}

        courses[course]["tees"][tee] = {
            "slope": slope,
            "rating": rating,
            "par": par,
        }

    return courses


def full_load_course_data(df: pd.DataFrame):
    data = convert_course_excel_to_json(df)
    _, sha = github_load_json("data/course_data.json")
    github_save_json("data/course_data.json", data, sha=sha)

def delta_load_course_data(df: pd.DataFrame):
    existing, sha = github_load_json("data/course_data.json")
    if existing is None:
        existing = {}

    incoming = convert_course_excel_to_json(df)

    for course, data in incoming.items():
        if course not in existing:
            existing[course] = data
        else:
            existing[course].setdefault("tees", {})
            existing[course]["tees"].update(data["tees"])

    github_save_json("data/course_data.json", existing, sha=sha)

# -------------------------------------------------------------------
# PLAYERS SECTION
# -------------------------------------------------------------------
def convert_players_excel_to_json(df):
    required_cols = ["Name", "membership_number", "Handicap Index Cap", "Email"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Players.xlsx: {missing}")

    nickname_cols = ["Nick1", "Nick2", "Nick3", "Nick4"]
    for col in nickname_cols:
        if col not in df.columns:
            df[col] = None

    players = []

    for _, row in df.iterrows():
        name = safe_str(row.get("Name"))
        membership = safe_str(row.get("membership_number"))
        handicap_index = safe_float(row.get("Handicap Index Cap"))
        team = safe_str(row.get("Team")) if "Team" in df.columns else None

        if not name or not membership:
            continue

        players.append({
            "name": name,
            "membership": membership,
            "handicap_index": handicap_index,
            "team": team,
            "email": safe_str(row.get("Email")),
            "Nick1": safe_str(row.get("Nick1")),
            "Nick2": safe_str(row.get("Nick2")),
            "Nick3": safe_str(row.get("Nick3")),
            "Nick4": safe_str(row.get("Nick4")),
        })

    return players


def full_load_players(df: pd.DataFrame):
    data = convert_players_excel_to_json(df)
    _, sha = github_load_json("data/players.json")
    github_save_json("data/players.json", data, sha=sha)

def delta_load_players(df: pd.DataFrame):
    existing, sha = github_load_json("data/players.json")
    if existing is None:
        existing = []

    incoming = convert_players_excel_to_json(df)

    existing_map = {p["membership"]: p for p in existing}

    for p in incoming:
        existing_map[p["membership"]] = p

    merged = list(existing_map.values())
    github_save_json("data/players.json", merged, sha=sha)

# -------------------------------------------------------------------
# PAIRINGS SECTION
# -------------------------------------------------------------------
def extract_month_and_course(df: pd.DataFrame):
    header_text = safe_str(df.iloc[0, 0])

    if ":" in header_text:
        month_part, _ = header_text.split(":", 1)
        month_key = month_part.strip()
    else:
        month_key = "Unknown"

    if "-" in header_text:
        course = header_text.split("-")[-1].strip()
    else:
        course = "Unknown Course"

    return month_key, course


def convert_pairings_excel_to_json(df: pd.DataFrame):
    month_key, course = extract_month_and_course(df)

    df = df.copy()
    df.columns = ["Fourball", "Player 1", "Player 2", "Player 3", "Player 4"]

    fourballs = []

    for _, row in df.iterrows():
        fb_raw = safe_str(row.get("Fourball"))
        if not fb_raw.isdigit():
            continue

        fb_no = int(fb_raw)
        players = []
        for col in ["Player 1", "Player 2", "Player 3", "Player 4"]:
            name = safe_str(row.get(col))
            if name:
                players.append(name)

        if not players:
            continue

        fourballs.append({
            "fourball": fb_no,
            "players": players,
        })

    return month_key, {
        "course": course,
        "fourballs": fourballs,
    }


def full_load_pairings(df: pd.DataFrame):
    month_key, data = convert_pairings_excel_to_json(df)
    _, sha = github_load_json("data/pairings.json")
    github_save_json("data/pairings.json", {month_key: data}, sha=sha)

def delta_load_pairings(df: pd.DataFrame):
    existing, sha = github_load_json("data/pairings.json")
    if existing is None:
        existing = {}

    month_key, data = convert_pairings_excel_to_json(df)

    existing[month_key] = data
    github_save_json("data/pairings.json", existing, sha=sha)

# -------------------------------------------------------------------
# GOAM SCORES SECTION
# -------------------------------------------------------------------
AI_CONFIG_PATH = "data/ai_config.json"


def load_ai_governance_config():
    config, sha = github_load_json(AI_CONFIG_PATH)
    if not isinstance(config, dict):
        config = {}

    defaults = {
        "zero_cost_mode": True,
        "parser_fallback_enabled": True,
        "low_confidence_threshold": 0.60,
        "min_regression_pass_rate": 0.85,
        "fast_model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "smart_model_id": "meta-llama/Llama-3.1-70B-Instruct",
        "high_accuracy_actions": ["compare_players", "compare_trends", "predict_next"],
    }

    merged = dict(defaults)
    merged.update(config)
    return merged, sha


def save_ai_governance_config(config: dict, sha=None):
    github_save_json(AI_CONFIG_PATH, config, sha=sha, message="Update AI governance config")


LEGACY_SHEET_MONTH_MAP = {
    "Akasia": "Feb'26",
    "PGC": "Mar'26",
    "Kyalami": "Apr'26",
    "CopperLeaf": "May'26",
    "Services": "Jun'26",
    "July": "Jul'26",
    "August": "Aug'26",
    "September": "Sep'26",
    "October": "Oct'26",
}

# Explicit aliases for common sheet/content variations.
COURSE_ALIAS_MAP = {
    "blue valley": "BlueValley",
    "bluevalley": "BlueValley",
    "blue valley golf & country": "BlueValley",
    "par 3 - blue valley golf estate": "BlueValley",
}


def _normalize_key(text):
    text = safe_str(text).lower()
    return "".join(ch for ch in text if ch.isalnum())


def _load_valid_course_names():
    valid = set()

    course_data, _ = github_load_json("data/course_data.json")
    if isinstance(course_data, dict):
        valid.update(safe_str(c) for c in course_data.keys() if safe_str(c))

    goam_scores, _ = github_load_json("data/goam_scores.json")
    if isinstance(goam_scores, dict):
        for month_data in goam_scores.values():
            if not isinstance(month_data, dict):
                continue
            course = safe_str(month_data.get("course"))
            if course:
                valid.add(course)

    valid.update(COURSE_ALIAS_MAP.values())
    return sorted(valid)


def _match_course_name(raw_value, valid_courses):
    value = safe_str(raw_value)
    if not value:
        return None

    key = _normalize_key(value)
    if not key:
        return None

    alias_lookup = {_normalize_key(k): v for k, v in COURSE_ALIAS_MAP.items()}
    if key in alias_lookup:
        return alias_lookup[key]

    valid_lookup = {_normalize_key(c): c for c in valid_courses}
    if key in valid_lookup:
        return valid_lookup[key]

    return None


def _infer_course_name(sheet_name, df, valid_courses):
    sheet_raw = safe_str(sheet_name)
    if _normalize_key(sheet_raw) not in {"sheet1", "sheet01"}:
        matched = _match_course_name(sheet_raw, valid_courses)
        if matched:
            return matched

    # Try explicit course columns.
    course_col = next(
        (
            col for col in df.columns
            if safe_str(col).lower().replace("_", " ") in {"course", "course name"}
        ),
        None,
    )
    if course_col is not None:
        for value in df[course_col].tolist():
            matched = _match_course_name(value, valid_courses)
            if matched:
                return matched

    # Try the first few cells for headings like "GOAM at Blue Valley".
    probe = df.head(12).iloc[:, : min(8, len(df.columns))]
    for row in probe.itertuples(index=False):
        for cell in row:
            text = safe_str(cell)
            if not text:
                continue
            matched = _match_course_name(text, valid_courses)
            if matched:
                return matched

    return None


def _normalize_month_key(raw_value, default_year=None):
    value = safe_str(raw_value)
    if not value:
        return None

    value = value.replace("’", "'")

    # Already in GOAM format.
    try:
        dt = datetime.strptime(value, "%b'%y")
        return dt.strftime("%b'%y")
    except Exception:
        pass

    parse_formats = [
        "%B", "%b",
        "%B %Y", "%b %Y", "%B %y", "%b %y",
        "%B-%Y", "%b-%Y", "%B-%y", "%b-%y",
        "%Y-%m", "%Y/%m", "%m/%Y", "%m/%y",
    ]

    for fmt in parse_formats:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt in {"%B", "%b"}:
                dt = dt.replace(year=default_year or datetime.now().year)
            return dt.strftime("%b'%y")
        except Exception:
            continue

    return None


def _infer_month_key(sheet_name, df):
    # Prefer explicit month-like sheet names for automatic future additions.
    inferred = _normalize_month_key(sheet_name)
    if inferred:
        return inferred

    # Try a Month column if present.
    month_col = next((c for c in df.columns if safe_str(c).lower() == "month"), None)
    if month_col is not None:
        for value in df[month_col].tolist():
            inferred = _normalize_month_key(value)
            if inferred:
                return inferred

    # Legacy fallback keeps historical workbook compatibility.
    if sheet_name in LEGACY_SHEET_MONTH_MAP:
        return LEGACY_SHEET_MONTH_MAP[sheet_name]

    # Keep data load moving even when month cannot be inferred.
    return safe_str(sheet_name) or "Unknown"


def compute_derived_fields(players):
    if not players:
        return {
            "best_gross": None,
            "best_nett": None,
            "ox_nau": None,
            "placements": [],
            "liv_totals": {},
            "pool_winner": None,
            "fines_total": 0,
        }

    best_gross_player = min(players, key=lambda p: p.get("strokes", 9999))
    best_gross = best_gross_player.get("name")

    for p in players:
        hcp = p.get("handicap")
        strokes = p.get("strokes")
        if hcp not in [None, "", 0] and strokes not in [None, ""]:
            try:
                p["nett"] = int(strokes) - int(hcp)
            except Exception:
                p["nett"] = None
        else:
            p["nett"] = None

    nett_players = [p for p in players if p.get("nett") is not None]
    best_nett = min(nett_players, key=lambda p: p["nett"])["name"] if nett_players else None

    ox_nau_player = min(players, key=lambda p: p.get("ips", 9999))
    ox_nau = ox_nau_player.get("name")

    placements_sorted = sorted(players, key=lambda p: p.get("ips", 0), reverse=True)
    placements = [
        {"position": i + 1, "name": p.get("name"), "ips": p.get("ips")}
        for i, p in enumerate(placements_sorted)
    ]

    team_map = {}
    for p in players:
        team = p.get("team", "")
        ips = p.get("ips", 0) or 0
        team_map.setdefault(team, []).append(ips)

    liv_totals = {
        team: sum(sorted(ips_list, reverse=True)[:3])
        for team, ips_list in team_map.items()
        if team
    }

    pool_players = [p for p in players if p.get("pool_payouts")]
    pool_winner = max(pool_players, key=lambda p: p.get("pool_payouts", 0)).get("name") if pool_players else None

    fines_total = sum([p.get("fines", 0) or 0 for p in players])

    return {
        "best_gross": best_gross,
        "best_nett": best_nett,
        "ox_nau": ox_nau,
        "placements": placements,
        "liv_totals": liv_totals,
        "pool_winner": pool_winner,
        "fines_total": fines_total,
    }


def convert_goam_scores_workbook_to_json(xls: dict):
    result = {}
    skipped = []
    valid_courses = _load_valid_course_names()

    for sheet_name, df in xls.items():
        if _normalize_key(sheet_name) in {"sheet1", "sheet01"}:
            skipped.append(
                {
                    "sheet": safe_str(sheet_name),
                    "reason": "Sheet1 is ignored by rule",
                }
            )
            continue

        month_key = _infer_month_key(sheet_name, df)
        course_name = _infer_course_name(sheet_name, df, valid_courses)
        if not course_name:
            skipped.append(
                {
                    "sheet": safe_str(sheet_name),
                    "reason": "No valid course name found in sheet content or alias mapping",
                }
            )
            continue

        df = df.copy()
        df.columns = [safe_str(c) for c in df.columns]

        players = []
        for _, row in df.iterrows():
            name = safe_str(row.get("Name"))
            if not name:
                continue

            strokes = safe_int(row.get("Strokes"))
            ips = safe_int(row.get("IPS"))
            team = safe_str(row.get("LIV"))

            player = {
                "name": name,
                "strokes": strokes,
                "ips": ips,
                "team": team,
            }

            for col in ["Handicap", "NP1", "NP2", "LD1", "LD2", "BG", "BN",
                        "Pool Bet", "Pool Payouts", "Fines"]:
                if col in df.columns:
                    key = col.lower().replace(" ", "_")
                    player[key] = safe_int(row.get(col))

            players.append(player)

        derived = compute_derived_fields(players)

        result[month_key] = {
            "course": course_name,
            "players": players,
            **derived,
        }

    return result, skipped


def full_load_goam_scores(xls: dict):
    data, skipped = convert_goam_scores_workbook_to_json(xls)
    _, sha = github_load_json("data/goam_scores.json")
    github_save_json("data/goam_scores.json", data, sha=sha)
    return skipped



def delta_load_goam_scores(xls: dict):
    existing, sha = github_load_json("data/goam_scores.json")
    if existing is None:
        existing = {}

    incoming, skipped = convert_goam_scores_workbook_to_json(xls)

    for month, data in incoming.items():
        existing[month] = data

    github_save_json("data/goam_scores.json", existing, sha=sha)
    return skipped

# -------------------------------------------------------------------
# MAIN PAGE
# -------------------------------------------------------------------
def show_data_manager_page():
    st.title("📂 Data Manager (Admin Only)")

    # ---------------- COURSES ----------------
    st.subheader("📘 Course Information")
    uploaded = st.file_uploader("Upload Course_Information.xlsx", type=["xlsx"])
    mode = st.radio("Load Mode", ["FULL", "DELTA"])

    if st.button("Process Course Data"):
        if not uploaded:
            st.error("Please upload Course_Information.xlsx.")
        else:
            try:
                df = pd.read_excel(uploaded)
                if mode == "FULL":
                    full_load_course_data(df)
                    st.success("Course data fully replaced.")
                else:
                    delta_load_course_data(df)
                    st.success("Course data merged (delta load).")

                data, sha = github_load_json("data/course_data.json")
                st.session_state["course_data"] = data
                st.session_state["course_data_sha"] = sha

            except Exception as e:
                st.error(f"Error processing course data: {e}")

    st.markdown("---")

    # ---------------- PLAYERS ----------------
    st.subheader("👥 Players")
    uploaded_players = st.file_uploader("Upload Players.xlsx", type=["xlsx"], key="players_upload")
    mode_players = st.radio("Load Mode (Players)", ["FULL", "DELTA"], key="players_mode")

    if st.button("Process Player Data"):
        if not uploaded_players:
            st.error("Please upload Players.xlsx.")
        else:
            try:
                df = pd.read_excel(uploaded_players)
                if mode_players == "FULL":
                    full_load_players(df)
                    st.success("Players fully replaced.")
                else:
                    delta_load_players(df)
                    st.success("Players merged (delta load).")

                data, sha = github_load_json("data/players.json")
                st.session_state["players"] = data
                st.session_state["players_sha"] = sha

            except Exception as e:
                st.error(f"Error processing player data: {e}")

    st.markdown("---")

    # ---------------- PAIRINGS ----------------
    st.subheader("⛳ Pairings (GOAM 4-Ball)")
    uploaded_pairings = st.file_uploader("Upload Pairings.xlsx", type=["xlsx"], key="pairings_upload")
    mode_pairings = st.radio("Load Mode (Pairings)", ["FULL", "DELTA"], key="pairings_mode")

    if st.button("Process Pairing Data"):
        if not uploaded_pairings:
            st.error("Please upload Pairings.xlsx.")
        else:
            try:
                df = pd.read_excel(uploaded_pairings, header=0)
                if mode_pairings == "FULL":
                    full_load_pairings(df)
                    st.success("Pairings fully replaced.")
                else:
                    delta_load_pairings(df)
                    st.success("Pairings merged (delta load).")

                data, sha = github_load_json("data/pairings.json")
                st.session_state["pairings"] = data
                st.session_state["pairings_sha"] = sha

            except Exception as e:
                st.error(f"Error processing pairing data: {e}")

    st.markdown("---")

    # ---------------- GOAM SCORES ----------------
    st.subheader("📘 GOAM Scores 2026 (with derived fields)")
    uploaded_scores = st.file_uploader(
        "Upload GOAM_Scores_2026_upload.xlsx",
        type=["xlsx"],
        key="goam_scores_upload",
    )
    mode_scores = st.radio("Load Mode (GOAM Scores)", ["FULL", "DELTA"], key="goam_scores_mode")

    if st.button("Process GOAM Scores 2026"):
        if not uploaded_scores:
            st.error("Please upload the GOAM_Scores_2026_upload.xlsx workbook.")
        else:
            try:
                xls = pd.read_excel(uploaded_scores, sheet_name=None)
                if mode_scores == "FULL":
                    skipped = full_load_goam_scores(xls)
                    st.success("GOAM scores fully replaced for 2026.")
                else:
                    skipped = delta_load_goam_scores(xls)
                    st.success("GOAM scores merged (delta load).")

                if skipped:
                    st.warning(
                        "Some sheets were skipped because no valid course name could be inferred "
                        "from sheet content or alias mapping."
                    )
                    st.dataframe(pd.DataFrame(skipped), hide_index=True, use_container_width=True)

                data, sha = github_load_json("data/goam_scores.json")
                st.session_state["goam_scores"] = data
                st.session_state["goam_scores_sha"] = sha

                # Keep local runtime file aligned with GitHub so leaderboards refresh immediately.
                if isinstance(data, dict):
                    with open("data/goam_scores.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)

            except Exception as e:
                st.error(f"Error processing GOAM scores: {e}")

    st.markdown("---")

    # ---------------- AI GOVERNANCE ----------------
    st.subheader("🤖 AI Governance")
    ai_cfg, ai_cfg_sha = load_ai_governance_config()

    zero_cost_mode = st.checkbox("Zero-cost mode default", value=bool(ai_cfg.get("zero_cost_mode", True)))
    parser_fallback_enabled = st.checkbox(
        "Parser LLM fallback enabled",
        value=bool(ai_cfg.get("parser_fallback_enabled", True)),
        help="Used only when zero-cost mode is disabled.",
    )

    low_conf_threshold = st.slider(
        "Low-confidence threshold",
        min_value=0.0,
        max_value=1.0,
        value=float(ai_cfg.get("low_confidence_threshold", 0.60)),
        step=0.05,
    )

    min_regression_pass_rate = st.slider(
        "Minimum regression pass rate (deploy gate)",
        min_value=0.0,
        max_value=1.0,
        value=float(ai_cfg.get("min_regression_pass_rate", 0.85)),
        step=0.05,
    )

    fast_model_id = st.text_input("Fast model ID", value=str(ai_cfg.get("fast_model_id", "")))
    smart_model_id = st.text_input("Smart model ID", value=str(ai_cfg.get("smart_model_id", "")))
    high_accuracy_actions_text = st.text_input(
        "High-accuracy actions (comma-separated)",
        value=", ".join(ai_cfg.get("high_accuracy_actions", [])),
    )

    if st.button("Save AI Governance Config"):
        actions = [a.strip() for a in high_accuracy_actions_text.split(",") if a.strip()]
        updated = {
            "zero_cost_mode": zero_cost_mode,
            "parser_fallback_enabled": parser_fallback_enabled,
            "low_confidence_threshold": float(low_conf_threshold),
            "min_regression_pass_rate": float(min_regression_pass_rate),
            "fast_model_id": fast_model_id.strip() or "meta-llama/Llama-3.1-8B-Instruct",
            "smart_model_id": smart_model_id.strip() or "meta-llama/Llama-3.1-70B-Instruct",
            "high_accuracy_actions": actions,
        }
        save_ai_governance_config(updated, sha=ai_cfg_sha)
        st.success("AI governance config saved.")

    # ---------------- DOWNLOAD SECTION ----------------
    st.subheader("⬇️ Download Data Files (CSV Format)")

    data_files = {
        "Course Data": "data/course_data.json",
        "Players": "data/players.json",
        "Pairings": "data/pairings.json",
        "GOAM Scores": "data/goam_scores.json",
    }

    for label, path in data_files.items():
        try:
            data, sha = github_load_json(path)

            if isinstance(data, dict):
                df = pd.json_normalize(data, sep="_")
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                st.warning(f"Unsupported format in {label}")
                continue

            csv_bytes = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                label=f"Download {label} (CSV)",
                data=csv_bytes,
                file_name=f"{label.replace(' ', '_').lower()}.csv",
                mime="text/csv",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Error converting {label} to CSV: {e}")
