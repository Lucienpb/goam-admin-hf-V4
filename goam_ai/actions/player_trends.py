from datetime import datetime

import numpy as np


def _month_order_value(value):
    if value is None:
        return datetime.min
    raw = str(value).strip().replace("’", "'")
    if not raw:
        return datetime.min
    for fmt in ("%b'%y", "%B %Y", "%b %Y", "%B-%Y", "%b-%Y", "%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return datetime.min


def _calc_slope(values):
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    m, _ = np.polyfit(x, y, 1)
    return float(m)


def _as_int_list(values):
    return [int(round(float(v))) for v in values]


def player_trends(df, min_rounds: int = 4):
    needed = {"player", "month", "ips"}
    if df is None or df.empty:
        return {"error": "No GOAM scores found to analyze"}
    if any(c not in df.columns for c in needed):
        return {"error": "Player trend analysis needs player, month and ips columns"}

    work = df.dropna(subset=["player", "month", "ips"]).copy()
    if work.empty:
        return {"error": "No complete rows found for trend analysis"}

    work["ips"] = work["ips"].astype(float)
    # Ignore zero/negative IPS placeholders; these are typically missing-score artifacts.
    work = work[work["ips"] > 0].copy()
    if work.empty:
        return {"error": "No valid IPS rounds found for trend analysis"}
    work["_month_order"] = work["month"].map(_month_order_value)

    player_rows = []
    for player, g in work.groupby("player"):
        g = g.sort_values("_month_order")
        ips_vals = g["ips"].tolist()
        if len(ips_vals) < min_rounds:
            continue

        last3 = ips_vals[-3:] if len(ips_vals) >= 3 else ips_vals
        prev3 = ips_vals[-6:-3] if len(ips_vals) >= 6 else ips_vals[:-3]
        recent_avg = float(np.mean(last3)) if last3 else float(np.mean(ips_vals))
        previous_avg = float(np.mean(prev3)) if prev3 else float(np.mean(ips_vals))
        momentum = recent_avg - previous_avg
        slope = _calc_slope(ips_vals)
        volatility = float(np.std(np.array(ips_vals, dtype=float), ddof=0))

        player_rows.append(
            {
                "player": player,
                "ips_series": _as_int_list(ips_vals),
                "months": [str(m) for m in g["month"].tolist()],
                "rounds": int(len(ips_vals)),
                "avg_ips": float(np.mean(ips_vals)),
                "recent_avg": recent_avg,
                "previous_avg": previous_avg,
                "momentum": float(momentum),
                "slope": float(slope),
                "volatility": volatility,
                "best_round": int(round(float(np.max(ips_vals)))),
                "last_round": int(round(float(ips_vals[-1]))),
            }
        )

    if not player_rows:
        return {"error": "Not enough player history to compute trends"}

    positive_movers = [r for r in player_rows if r["momentum"] > 0]
    hottest = sorted(
        positive_movers if positive_movers else player_rows,
        key=lambda r: (r["momentum"], r["recent_avg"], r["avg_ips"]),
        reverse=True,
    )[:3]
    dipping = sorted(player_rows, key=lambda r: (r["momentum"], -r["recent_avg"], -r["avg_ips"]))[:3]
    consistency = sorted(player_rows, key=lambda r: (r["volatility"], -r["avg_ips"], -r["rounds"]))[:3]

    power_rank = sorted(
        player_rows,
        key=lambda r: (
            (0.45 * r["recent_avg"]) + (0.35 * r["momentum"]) + (0.20 * r["slope"] * 10.0),
            r["avg_ips"],
        ),
        reverse=True,
    )[:5]

    best_single = max(player_rows, key=lambda r: r["best_round"])

    return {
        "events": sorted(work["month"].astype(str).unique().tolist(), key=_month_order_value),
        "players_analyzed": int(len(player_rows)),
        "hottest": hottest,
        "dipping": dipping,
        "consistent": consistency,
        "power_ranking": power_rank,
        "best_single_round": {
            "player": best_single["player"],
            "ips": int(best_single["best_round"]),
        },
    }
