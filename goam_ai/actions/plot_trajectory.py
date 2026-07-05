import pandas as pd

def plot_trajectory(df, player: str, metric="ips", rounds=None):
    pdf = df[df["player"] == player].sort_values("month")

    if pdf.empty:
        return {"error": f"No data for {player}"}

    if rounds:
        pdf = pdf.tail(rounds)

    return {
        "player": player,
        "metric": metric,
        "months": pdf["month"].tolist(),
        "values": [float(v) for v in pdf[metric].tolist()],
    }

