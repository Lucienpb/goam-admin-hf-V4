def player_monthly_scores(df, player: str):
    """
    Return monthly IPS and strokes scores for a specific player.
    """
    pdf = df[df["player"] == player].sort_values("month")

    if pdf.empty:
        return {"error": f"No data found for player {player}"}

    # Build monthly breakdown
    monthly_data = []
    for month in pdf["month"].unique():
        month_df = pdf[pdf["month"] == month]
        row = month_df.iloc[0]  # Get first entry for that month
        
        monthly_data.append({
            "month": month,
            "course": row["course"],
            "ips": int(row["ips"]),
            "strokes": int(row["strokes"]),
            "team": row["team"]
        })

    return {
        "player": player,
        "monthly_scores": monthly_data,
        "total_rounds": len(pdf),
        "avg_ips": float(pdf["ips"].mean()),
        "best_ips": int(pdf["ips"].max()),
        "worst_ips": int(pdf["ips"].min())
    }
