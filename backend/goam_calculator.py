#---------------------------------
# GOAM Calculator
#---------------------------------
import pandas as pd
from datetime import datetime


class GOAMCalculator:
    """
    Performs all GOAM calculations:
    - Build long-format rounds from course sheets / JSON
    - IPS best six
    - Strokes best six (over par)
    - IPS leaderboard (Excel layout)
    - Strokes leaderboard (Excel layout)
    - LIV team scores + LIV leaderboard
    - Split by course
    - Dynamic course list
    - Output filename
    """

    PAR = 72

    @staticmethod
    def _month_sort_value(value):
        if value is None:
            return None

        raw = str(value).strip().replace("’", "'")
        if not raw:
            return None

        for fmt in ("%b'%y", "%B %Y", "%b %Y", "%B-%Y", "%b-%Y", "%Y-%m", "%Y/%m"):
            try:
                return datetime.strptime(raw, fmt)
            except Exception:
                continue

        return None

    @staticmethod
    def _ordered_courses(df):
        if df.empty:
            return []

        course_col = None
        for col in df.columns:
            if col.strip().lower() == "course":
                course_col = col
                break

        if not course_col:
            return []

        # Preserve first-seen order as fallback.
        first_seen = []
        seen = set()
        for raw_course in df[course_col].tolist():
            course = str(raw_course).strip()
            if not course or course in seen:
                continue
            seen.add(course)
            first_seen.append(course)

        if "Month" not in df.columns:
            return first_seen

        month_map = {}
        for _, row in df[[course_col, "Month"]].dropna(subset=[course_col]).iterrows():
            course = str(row[course_col]).strip()
            if not course:
                continue
            parsed_month = GOAMCalculator._month_sort_value(row.get("Month"))
            if parsed_month is None:
                continue
            if course not in month_map or parsed_month > month_map[course]:
                month_map[course] = parsed_month

        if not month_map:
            return first_seen

        ordered = [course for course, _ in sorted(month_map.items(), key=lambda item: item[1])]
        for course in first_seen:
            if course not in ordered:
                ordered.append(course)

        return ordered

    @staticmethod
    def get_active_courses(df):
        return GOAMCalculator._ordered_courses(df)

    # ---------------------------------------------------------
    # Build from course sheets
    # ---------------------------------------------------------
    @staticmethod
    def build_from_course_sheets(sheets_dict):
        rows = []

        for sheet_name, df in sheets_dict.items():
            if not {"Name", "Strokes", "IPS"}.issubset(df.columns):
                continue

            for _, row in df.iterrows():
                rows.append({
                    "Name": row["Name"],
                    "Course": sheet_name,
                    "Strokes": row["Strokes"],
                    "IPS": row["IPS"],
                    "Team": row["LIV"] if "LIV" in df.columns else None,
                })

        if not rows:
            return pd.DataFrame(columns=["Name", "Course", "Strokes", "IPS", "Team"])

        return pd.DataFrame(rows)

    # ---------------------------------------------------------
    # List courses
    # ---------------------------------------------------------
    @staticmethod
    def list_courses(df):
        return GOAMCalculator.get_active_courses(df)

    # ---------------------------------------------------------
    # Best 6 IPS
    # ---------------------------------------------------------
    @staticmethod
    def calculate_best_six_ips(df):
        if df.empty or "IPS" not in df.columns:
            return pd.DataFrame(columns=["Name", "Best6_IPS", "Rounds_Played"])

        results = []

        for name, group in df.groupby("Name"):
            best6 = group["IPS"].nlargest(6).sum()
            results.append({
                "Name": name,
                "Best6_IPS": best6,
                "Rounds_Played": len(group),
            })

        out = pd.DataFrame(results)

        out = out.sort_values(
            by=["Best6_IPS", "Rounds_Played"],
            ascending=[False, False],
        ).reset_index(drop=True)

        return out

    # ---------------------------------------------------------
    # Best 6 Strokes
    # ---------------------------------------------------------
    @staticmethod
    def calculate_strokes(df):
        if df.empty or "Strokes" not in df.columns:
            return pd.DataFrame(columns=["Name", "Games_Played", "Best6_Strokes_Over_Par"])

        df = df.copy()
        df["Strokes_Over_Par"] = df["Strokes"] - GOAMCalculator.PAR

        results = []

        for name, group in df.groupby("Name"):
            games = len(group)
            best6 = group["Strokes_Over_Par"].nsmallest(6).sum()
            results.append({
                "Name": name,
                "Games_Played": games,
                "Best6_Strokes_Over_Par": best6,
            })

        out = pd.DataFrame(results)

        out = out.sort_values(
            by=["Games_Played", "Best6_Strokes_Over_Par"],
            ascending=[False, True],
        ).reset_index(drop=True)

        return out

    # ---------------------------------------------------------
    # LIV scoring
    # ---------------------------------------------------------
    @staticmethod
    def calculate_liv(df):
        if df.empty:
            return pd.DataFrame(columns=["Team", "Course", "LIV_Points"])

        # Auto-detect course column
        course_col = None
        for col in df.columns:
            if col.strip().lower() == "course":
                course_col = col
                break

        if not course_col or "Team" not in df.columns:
            return pd.DataFrame(columns=["Team", "Course", "LIV_Points"])

        results = []

        for (course, team), group in df.groupby([course_col, "Team"]):
            if team is None:
                continue
            top3 = group["IPS"].nlargest(3).sum()
            results.append({
                "Team": team,
                "Course": course,
                "LIV_Points": top3,
            })

        if not results:
            return pd.DataFrame(columns=["Team", "Course", "LIV_Points"])

        out = pd.DataFrame(results)

        out = out.sort_values(
            by=["Course", "LIV_Points"],
            ascending=[True, False],
        ).reset_index(drop=True)

        return out

    # ---------------------------------------------------------
    # LIV Leaderboard
    # ---------------------------------------------------------
    @staticmethod
    def build_liv_leaderboard(df):
        liv_raw = GOAMCalculator.calculate_liv(df)

        if liv_raw.empty:
            return pd.DataFrame()

        pivot = liv_raw.pivot_table(
            index="Team",
            columns="Course",
            values="LIV_Points",
            aggfunc="first",
        ).fillna(0)

        # Business override requested for legacy scoring corrections.
        tee_tigers_overrides = {
            "Akasia": 186,
            "PGC": 0,
            "Kyalami": 0,
        }
        if "Tee Tigers" in pivot.index:
            for course_name, course_value in tee_tigers_overrides.items():
                if course_name not in pivot.columns:
                    pivot[course_name] = 0
                pivot.loc["Tee Tigers", course_name] = course_value

        active = GOAMCalculator.get_active_courses(df)
        active = [c for c in active if c in pivot.columns]

        pivot["LIV Total"] = pivot[active].sum(axis=1)

        played_counts = pivot[active].astype(bool).sum(axis=1)
        pivot["Strength Index"] = (
            pivot[active].sum(axis=1) / played_counts.replace(0, pd.NA)
        ).round(1)

        trend = []
        for team in pivot.index:
            if len(active) < 2:
                trend.append("–")
            else:
                current_avg = pivot.loc[team, active].mean()
                prev_avg = pivot.loc[team, active[:-1]].mean()
                trend.append("↑" if current_avg > prev_avg else "↓" if current_avg < prev_avg else "→")

        pivot["Trend Index"] = trend

        pivot = pivot.sort_values(by="LIV Total", ascending=False)

        final_cols = ["LIV Total", "Strength Index", "Trend Index"] + active
        final = pivot[final_cols].reset_index()

        return final

    # ---------------------------------------------------------
    # IPS Leaderboard
    # ---------------------------------------------------------
    @staticmethod
    def build_ips_leaderboard(df):
        if df.empty or "IPS" not in df.columns:
            return pd.DataFrame()

        course_col = None
        for col in df.columns:
            if col.strip().lower() == "course":
                course_col = col
                break

        if not course_col:
            return pd.DataFrame()

        pivot = df.pivot_table(
            index="Name",
            columns=course_col,
            values="IPS",
            aggfunc="first",
        ).reset_index()

        best6 = GOAMCalculator.calculate_best_six_ips(df)

        merged = pivot.merge(best6, on="Name", how="left").fillna(0)

        merged["IPS"] = (
            df.groupby("Name")["IPS"]
            .sum()
            .reindex(merged["Name"])
            .fillna(0)
            .astype(int)
            .values
        )

        numeric_cols = merged.columns.drop(["Name"])
        merged[numeric_cols] = merged[numeric_cols].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0)

        merged = merged.sort_values(
            by=["Best6_IPS", "Rounds_Played"],
            ascending=[False, False],
        ).reset_index(drop=True)

        # Shared positions — only show position on first of each tied group
        positions = []
        display_positions = []
        rank = 1
        prev_score = None
        prev_rank = 1
        for i, (_, row) in enumerate(merged.iterrows()):
            score = (row["Best6_IPS"], row["Rounds_Played"])
            if i == 0:
                positions.append(rank)
                display_positions.append(rank)
                prev_score = score
                prev_rank = rank
            else:
                if score == prev_score:
                    positions.append(prev_rank)
                    display_positions.append("")  # blank for tied players after first
                else:
                    rank = i + 1  # correct: position = row number (1-based)
                    positions.append(rank)
                    display_positions.append(rank)
                    prev_rank = rank
                prev_score = score

        merged["Position"] = positions        # numeric for movement calc
        merged["Pos"] = display_positions     # display version

        active = GOAMCalculator.get_active_courses(df)
        active = [c for c in active if c in merged.columns]

        merged["Avg_IPS"] = (merged["IPS"] / merged["Rounds_Played"].replace(0, pd.NA)).round(1)

        final_cols = ["Pos", "Name", "IPS", "Best6_IPS"] + active + ["Avg_IPS", "Rounds_Played"]

        return merged[["Position"] + final_cols]

    # ---------------------------------------------------------
    # Strokes Leaderboard
    # ---------------------------------------------------------
    @staticmethod
    def build_strokes_leaderboard(df):
        if df.empty or "Strokes" not in df.columns:
            return pd.DataFrame()

        df = df.copy()
        df["Strokes_Over_Par"] = df["Strokes"] - GOAMCalculator.PAR

        # Auto-detect course column
        course_col = None
        for col in df.columns:
            if col.strip().lower() == "course":
                course_col = col
                break

        if not course_col:
            return pd.DataFrame()

        pivot = df.pivot_table(
            index="Name",
            columns=course_col,
            values="Strokes_Over_Par",
            aggfunc="first",
        ).reset_index()

        best6 = GOAMCalculator.calculate_strokes(df)

        merged = pivot.merge(best6, on="Name", how="left").fillna(0)

        numeric_cols = merged.columns.drop(["Name"])
        merged[numeric_cols] = merged[numeric_cols].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0)

        merged = merged.sort_values(
            by=["Games_Played", "Best6_Strokes_Over_Par"],
            ascending=[False, True],
        ).reset_index(drop=True)

        merged.insert(0, "Rank", merged.index + 1)

        active = GOAMCalculator.get_active_courses(df)
        active = [c for c in active if c in merged.columns]

        final_cols = ["Rank", "Name", "Best6_Strokes_Over_Par"] + active + ["Games_Played"]

        return merged[final_cols]

    # ---------------------------------------------------------
    # Split by course
    # ---------------------------------------------------------
    @staticmethod
    def split_by_course(df):
        if df.empty:
            return {}

        # Auto-detect course column
        course_col = None
        for col in df.columns:
            if col.strip().lower() == "course":
                course_col = col
                break

        if not course_col:
            return {}

        result = {}
        for course, group in df.groupby(course_col):
            cols = [c for c in ["Name", "Strokes", "IPS", "Team"] if c in group.columns]
            result[course] = group[cols].reset_index(drop=True)
        return result

    # ---------------------------------------------------------
    # Output filename
    # ---------------------------------------------------------
    @staticmethod
    def generate_output_filename():
        month = datetime.now().strftime("%b")
        return f"GOAM_Scores_2026_{month}_updated.xlsx"

    # ---------------------------------------------------------
    # Position Movement
    # Compares position before vs after the latest course
    # ---------------------------------------------------------
    @staticmethod
    def calculate_position_movement(df):
        """
        Returns a dict {player_name: movement_string}
        e.g. {"Lucien Barnes": "⬆️ 2", "Arno Adonis": "⬇️ 1", ...}
        """
        active = GOAMCalculator.get_active_courses(df)

        if len(active) < 2:
            # Only one course played — no movement yet
            return {}

        latest_course = active[-1]
        prev_courses = active[:-1]

        # Leaderboard WITHOUT latest course
        df_prev = df[df["Course"].isin(prev_courses)]
        lb_prev = GOAMCalculator.build_ips_leaderboard(df_prev)

        # Full leaderboard WITH latest course
        lb_full = GOAMCalculator.build_ips_leaderboard(df)

        if lb_prev.empty or lb_full.empty:
            return {}

        prev_positions = {row["Name"]: int(row["Position"]) for _, row in lb_prev.iterrows()}
        full_positions = {row["Name"]: int(row["Position"]) for _, row in lb_full.iterrows()}

        movement = {}
        for name, curr_pos in full_positions.items():
            prev_pos = prev_positions.get(name)
            if prev_pos is None:
                movement[name] = "🆕"
            else:
                delta = prev_pos - curr_pos  # positive = moved up
                if delta > 0:
                    movement[name] = f"⬆️ {delta}"
                elif delta < 0:
                    movement[name] = f"⬇️ {abs(delta)}"
                else:
                    movement[name] = "➡️"

        return movement

    # ---------------------------------------------------------
    # Build from JSON
    # ---------------------------------------------------------
    @staticmethod
    def build_from_json(goam_scores):
        rows = []
        for month, data in goam_scores.items():
            course = data.get("course", "")
#            if str(course).strip().lower() == "services":
#                continue  # hard exclude

            for p in data.get("players", []):
                rows.append({
                    "Name": p.get("name"),
                    "Strokes": p.get("strokes"),
                    "IPS": p.get("ips"),
                    "Course": course,
                    "Month": month,
                    "Team": p.get("team"),
                })

        return pd.DataFrame(rows)

