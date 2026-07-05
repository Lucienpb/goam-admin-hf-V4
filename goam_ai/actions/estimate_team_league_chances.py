import numpy as np


def estimate_team_league_chances(df, team: str, games_left: int = 2, simulations: int = 3000):
    required = {"team", "course", "ips"}
    if any(col not in df.columns for col in required):
        return {"error": "Team league chance calculation needs team, course and ips columns"}

    teams = [t for t in df["team"].dropna().unique().tolist() if str(t).strip()]
    if team not in teams:
        return {"error": f"No data found for team {team}"}

    games_left = max(1, min(12, int(games_left or 2)))
    simulations = max(500, min(10000, int(simulations or 3000)))

    # Current team totals from historical rounds: per course, sum top-3 IPS per team.
    team_course_scores = {}
    for (course, tname), group in df.groupby(["course", "team"]):
        if tname is None:
            continue
        ips_vals = group["ips"].dropna().astype(float).tolist()
        if not ips_vals:
            continue
        team_course_scores.setdefault(tname, []).append(float(sum(sorted(ips_vals, reverse=True)[:3])))

    if team not in team_course_scores:
        return {"error": f"No usable IPS history found for team {team}"}

    profiles = {}
    for tname, values in team_course_scores.items():
        if not values:
            continue
        mean_val = float(np.mean(values))
        std_val = float(np.std(values, ddof=0))
        if std_val < 3.0:
            std_val = 8.0
        profiles[tname] = {
            "existing_scores": values,
            "current_total": float(sum(values)),
            "mean": mean_val,
            "std": std_val,
        }

    if team not in profiles:
        return {"error": f"No usable scoring profile found for team {team}"}

    current_scores = sorted(
        [(name, p["current_total"]) for name, p in profiles.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    current_rank = next((idx + 1 for idx, (name, _) in enumerate(current_scores) if name == team), None)
    leader_name, leader_score = current_scores[0]
    team_score = profiles[team]["current_total"]
    gap_to_leader = float(leader_score - team_score)

    rng = np.random.default_rng(42)
    win_score = 0.0
    podium_hits = 0
    names = list(profiles.keys())

    for _ in range(simulations):
        final_scores = {}
        for tname in names:
            p = profiles[tname]
            simulated = rng.normal(loc=p["mean"], scale=p["std"], size=games_left)
            simulated = np.clip(simulated, 0, 180)
            final_scores[tname] = float(p["current_total"] + simulated.sum())

        max_score = max(final_scores.values())
        winners = [n for n, s in final_scores.items() if abs(s - max_score) < 1e-9]
        if team in winners:
            win_score += 1.0 / len(winners)

        ranked_scores = sorted(final_scores.values(), reverse=True)
        podium_cut = ranked_scores[min(2, len(ranked_scores) - 1)]
        if final_scores[team] >= podium_cut:
            podium_hits += 1

    return {
        "team": team,
        "games_left": games_left,
        "simulations": simulations,
        "current_rank": current_rank,
        "current_total": round(team_score, 1),
        "leader": leader_name,
        "leader_total": round(float(leader_score), 1),
        "gap_to_leader": round(gap_to_leader, 1),
        "win_probability": round(float(win_score / simulations), 4),
        "podium_probability": round(float(podium_hits / simulations), 4),
        "assumption": "Monte Carlo estimate using each team's historical top-3 IPS-per-round profile.",
    }
