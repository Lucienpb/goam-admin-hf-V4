def compare_players(df, players: list, metric="ips"):
    if len(players) < 2:
        return {"error": "compare_players requires at least 2 players"}

    stats = []
    for p in players:
        d = df[df["player"] == p]
        if d.empty:
            continue
        stats.append({
            "name": p,
            "avg": round(float(d[metric].mean()), 1),
            "best": round(float(d[metric].max()), 1),
            "worst": round(float(d[metric].min()), 1),
            "rounds": len(d),
        })

    if not stats:
        return {"error": "No data found for any of the specified players"}

    # higher is better for IPS, lower is better for strokes
    winner = max(stats, key=lambda x: x["avg"]) if metric == "ips" else min(stats, key=lambda x: x["avg"])

    return {
        "players": stats,
        "metric": metric,
        "winner": winner["name"],
    }
