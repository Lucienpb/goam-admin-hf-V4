def season_insights(df):
    required = {"player", "team", "course", "ips"}
    if df is None or df.empty:
        return {"error": "No GOAM scores found to analyze"}
    if any(col not in df.columns for col in required):
        return {"error": "Season insights require player, team, course and ips columns"}

    work = df.copy()
    work = work.dropna(subset=["player", "team", "course", "ips"])
    if work.empty:
        return {"error": "No complete rows found for season analysis"}

    work["ips"] = work["ips"].astype(float)

    # Team LIV points proxy: per course, sum each team's top-3 IPS.
    team_course = (
        work.groupby(["course", "team"])["ips"]
        .apply(lambda s: float(s.nlargest(3).sum()))
        .reset_index(name="course_points")
    )
    team_totals = (
        team_course.groupby("team", as_index=False)["course_points"]
        .sum()
        .sort_values("course_points", ascending=False)
        .reset_index(drop=True)
    )
    team_totals["course_points"] = team_totals["course_points"].round(1)

    # Player profile.
    player_stats = (
        work.groupby("player", as_index=False)
        .agg(total_ips=("ips", "sum"), avg_ips=("ips", "mean"), rounds=("ips", "count"))
        .sort_values(["total_ips", "avg_ips"], ascending=[False, False])
        .reset_index(drop=True)
    )
    player_stats["total_ips"] = player_stats["total_ips"].round(1)
    player_stats["avg_ips"] = player_stats["avg_ips"].round(1)

    max_rounds = int(player_stats["rounds"].max()) if not player_stats.empty else 1
    player_stats["consistency_score"] = player_stats["avg_ips"] * (player_stats["rounds"] / max_rounds)
    consistency = player_stats.sort_values(["consistency_score", "total_ips"], ascending=[False, False]).iloc[0]

    challengers = player_stats[player_stats["player"] != consistency["player"]].head(3)

    rounds_total = int(len(work))
    events_total = int(work["course"].nunique())

    top_team = team_totals.iloc[0] if not team_totals.empty else None
    second_team = team_totals.iloc[1] if len(team_totals) > 1 else None

    participation = player_stats.sort_values(["rounds", "total_ips"], ascending=[False, False]).head(3)
    high_avg_low_rounds = player_stats[player_stats["rounds"] < max_rounds]
    if not high_avg_low_rounds.empty:
        high_avg_low_rounds = high_avg_low_rounds.sort_values(["avg_ips", "total_ips"], ascending=[False, False]).iloc[0]
    else:
        high_avg_low_rounds = None

    best_row = work.sort_values("ips", ascending=False).iloc[0]

    tight_mid_pack_gap = None
    if len(team_totals) >= 4:
        second = float(team_totals.iloc[1]["course_points"])
        fourth = float(team_totals.iloc[3]["course_points"])
        tight_mid_pack_gap = round(second - fourth, 1)

    return {
        "dataset_label": "current GOAM scores",
        "events_total": events_total,
        "rounds_total": rounds_total,
        "team_standings": team_totals.to_dict(orient="records"),
        "top_team": {
            "team": str(top_team["team"]) if top_team is not None else None,
            "points": float(top_team["course_points"]) if top_team is not None else None,
            "gap_to_second": round(float(top_team["course_points"] - second_team["course_points"]), 1)
            if top_team is not None and second_team is not None
            else None,
        },
        "most_consistent_player": {
            "player": str(consistency["player"]),
            "total_ips": float(consistency["total_ips"]),
            "avg_ips": float(consistency["avg_ips"]),
            "rounds": int(consistency["rounds"]),
        },
        "challengers": challengers[["player", "total_ips", "avg_ips", "rounds"]].to_dict(orient="records"),
        "participation_leaders": participation[["player", "total_ips", "avg_ips", "rounds"]].to_dict(orient="records"),
        "high_avg_low_rounds": (
            {
                "player": str(high_avg_low_rounds["player"]),
                "total_ips": float(high_avg_low_rounds["total_ips"]),
                "avg_ips": float(high_avg_low_rounds["avg_ips"]),
                "rounds": int(high_avg_low_rounds["rounds"]),
            }
            if high_avg_low_rounds is not None
            else None
        ),
        "best_single_round": {
            "player": str(best_row["player"]),
            "course": str(best_row["course"]),
            "ips": float(best_row["ips"]),
        },
        "tight_mid_pack_gap": tight_mid_pack_gap,
    }
