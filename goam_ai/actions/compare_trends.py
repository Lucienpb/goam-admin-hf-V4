import numpy as np
import pandas as pd

def _slope(series: pd.Series) -> float:
    if len(series) < 2:
        return 0.0
    x = np.arange(len(series))
    y = series.values
    A = np.vstack([x, np.ones(len(x))]).T
    m, _ = np.linalg.lstsq(A, y, rcond=None)[0]
    return float(m)

def compare_trends(df, players: list, metric="ips", window=3):
    if len(players) != 2:
        return {"error": "compare_trends requires exactly 2 players"}

    p1, p2 = players

    # Sort by month string (Feb'26, Mar'26, etc.)
    d1 = df[df["player"] == p1].sort_values("month")
    d2 = df[df["player"] == p2].sort_values("month")

    if len(d1) < window or len(d2) < window:
        return {"error": "Not enough rounds to compute trends"}

    t1 = float(d1[metric].tail(window).mean())
    t2 = float(d2[metric].tail(window).mean())

    return {
        "players": players,
        "metric": metric,
        "window": window,
        "p1_trend": t1,
        "p2_trend": t2,
        "trend_diff": t1 - t2,
    }


