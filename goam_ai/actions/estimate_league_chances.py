import numpy as np


def estimate_league_chances(df, player: str, games_left: int = 2, simulations: int = 3000):
    if "player" not in df.columns or "ips" not in df.columns:
        return {"error": "League chance calculation needs player and ips columns"}

    if player not in df["player"].dropna().tolist():
        return {"error": f"No data found for player {player}"}

    games_left = max(1, min(12, int(games_left or 2)))
    simulations = max(500, min(10000, int(simulations or 3000)))

    # Build player-level profile.
    profiles = {}
    for name, group in df.groupby("player"):
        ips_values = group["ips"].dropna().astype(float).tolist()
        if not ips_values:
            continue

        mean_ips = float(np.mean(ips_values))
        std_ips = float(np.std(ips_values, ddof=0))
        if std_ips < 1.0:
            std_ips = 2.5

        profiles[name] = {
            "existing_ips": ips_values,
            "mean": mean_ips,
            "std": std_ips,
            "current_best6": float(sum(sorted(ips_values, reverse=True)[:6])),
        }

    if player not in profiles:
        return {"error": f"No usable IPS history found for {player}"}

    # Current leaderboard position using Best 6.
    current_scores = sorted(
        [(name, vals["current_best6"]) for name, vals in profiles.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    current_rank = next((idx + 1 for idx, (name, _) in enumerate(current_scores) if name == player), None)
    leader_name, leader_score = current_scores[0]
    player_score = profiles[player]["current_best6"]
    gap_to_leader = float(leader_score - player_score)

    rng = np.random.default_rng(42)
    win_score = 0.0
    podium_hits = 0

    names = list(profiles.keys())

    for _ in range(simulations):
        final_scores = {}

        for name in names:
            p = profiles[name]
            simulated_rounds = rng.normal(loc=p["mean"], scale=p["std"], size=games_left)
            simulated_rounds = np.clip(simulated_rounds, 0, 50)

            combined = p["existing_ips"] + simulated_rounds.tolist()
            final_best6 = float(sum(sorted(combined, reverse=True)[:6]))
            final_scores[name] = final_best6

        max_score = max(final_scores.values())
        winners = [n for n, s in final_scores.items() if abs(s - max_score) < 1e-9]
        if player in winners:
            win_score += 1.0 / len(winners)

        ranked_scores = sorted(final_scores.values(), reverse=True)
        podium_cut = ranked_scores[min(2, len(ranked_scores) - 1)]
        if final_scores[player] >= podium_cut:
            podium_hits += 1

    win_probability = float(win_score / simulations)
    podium_probability = float(podium_hits / simulations)

    return {
        "player": player,
        "games_left": games_left,
        "simulations": simulations,
        "current_rank": current_rank,
        "current_best6_ips": round(player_score, 1),
        "leader": leader_name,
        "leader_best6_ips": round(float(leader_score), 1),
        "gap_to_leader": round(gap_to_leader, 1),
        "win_probability": round(win_probability, 4),
        "podium_probability": round(podium_probability, 4),
        "assumption": "Monte Carlo estimate using each player's IPS mean and variance from recorded rounds; all players play remaining games.",
    }
