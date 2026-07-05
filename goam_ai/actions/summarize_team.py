def summarize_team(df, team: str):
    tdf = df[df["team"] == team]

    if tdf.empty:
        return {"error": f"No data found for team {team}"}

    return {
        "team": team,
        "players": sorted(tdf["player"].unique().tolist()),
        "rounds": len(tdf),
        "avg_ips": float(tdf["ips"].mean()),
        "best_ips": float(tdf["ips"].max()),
        "worst_ips": float(tdf["ips"].min()),
        "avg_strokes": float(tdf["strokes"].mean()),
    }
