import pandas as pd

def predict_next(df, player: str, metric="ips", window=3):
    if "player" not in df.columns:
        return {"error": "Prediction data is missing player column"}

    if metric not in df.columns:
        return {"error": f"Prediction metric '{metric}' is not available"}

    sort_col = "month" if "month" in df.columns else None

    pdf = df[df["player"] == player]
    if sort_col:
        pdf = pdf.sort_values(sort_col)

    if len(pdf) < window:
        return {"error": "Not enough rounds to predict"}

    recent = pdf[metric].tail(window).mean()

    return {
        "player": player,
        "metric": metric,
        "window": window,
        "predicted_next": float(recent),
    }
