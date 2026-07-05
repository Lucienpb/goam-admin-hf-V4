def summarize_player(df, player: str):
    pdf = df[df["player"] == player]

    if pdf.empty:
        return {"error": f"No data found for player {player}"}

    return {
        "player": player,
        "rounds": len(pdf),
        "avg_ips": float(pdf["ips"].mean()),
        "best_ips": float(pdf["ips"].max()),
        "worst_ips": float(pdf["ips"].min()),
        "avg_strokes": float(pdf["strokes"].mean()),
        "best_strokes": int(pdf["strokes"].min()),
        "worst_strokes": int(pdf["strokes"].max()),
        "teams": sorted(pdf["team"].unique().tolist()),
        "courses": sorted(pdf["course"].unique().tolist()),
        "months": sorted(pdf["month"].unique().tolist()),
    }

