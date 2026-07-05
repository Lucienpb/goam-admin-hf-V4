import pandas as pd

def json_to_df(goam_json: dict) -> pd.DataFrame:
    rows = []

    for month, data in goam_json.items():
        course = data.get("course")
        players = data.get("players", [])

        for p in players:
            rows.append({
                "month": month,
                "course": course,
                "player": p["name"],
                "strokes": p.get("strokes"),
                "ips": p.get("ips"),
                "nett": p.get("nett"),
                "team": p.get("team"),
            })

    return pd.DataFrame(rows)
