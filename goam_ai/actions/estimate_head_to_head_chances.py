import numpy as np


def estimate_head_to_head_chances(
    df,
    player_a: str,
    player_b: str,
    best_of: int = 6,
    total_games: int = 8,
    simulations: int = 3000,
):
    if "player" not in df.columns or "ips" not in df.columns:
        return {"error": "Head-to-head chance calculation needs player and ips columns"}

    if not player_a or not player_b:
        return {"error": "Two players are required for head-to-head chance analysis"}

    a_df = df[df["player"] == player_a]
    b_df = df[df["player"] == player_b]

    if a_df.empty or b_df.empty:
        return {"error": f"Missing data for one or both players: {player_a}, {player_b}"}

    best_of = max(1, min(12, int(best_of or 6)))
    total_games = max(best_of, min(20, int(total_games or 8)))
    simulations = max(500, min(10000, int(simulations or 3000)))

    a_vals = a_df["ips"].dropna().astype(float).tolist()
    b_vals = b_df["ips"].dropna().astype(float).tolist()

    if not a_vals or not b_vals:
        return {"error": "Insufficient IPS data for one or both players"}

    rounds_played = max(len(a_vals), len(b_vals))
    games_left = max(0, total_games - rounds_played)

    a_mean = float(np.mean(a_vals))
    b_mean = float(np.mean(b_vals))
    a_std = float(np.std(a_vals, ddof=0))
    b_std = float(np.std(b_vals, ddof=0))

    if a_std < 1.0:
        a_std = 2.5
    if b_std < 1.0:
        b_std = 2.5

    def best_score(values):
        return float(sum(sorted(values, reverse=True)[:best_of]))

    current_a = best_score(a_vals)
    current_b = best_score(b_vals)

    if games_left == 0:
        if abs(current_a - current_b) < 1e-9:
            return {
                "player_a": player_a,
                "player_b": player_b,
                "best_of": best_of,
                "total_games": total_games,
                "games_left": 0,
                "player_a_win_probability": 0.5,
                "player_b_win_probability": 0.5,
                "tie_probability": 1.0 if abs(current_a - current_b) < 1e-9 else 0.0,
                "current_a_best": round(current_a, 1),
                "current_b_best": round(current_b, 1),
                "assumption": "No games remaining; outcome is based on current best-of totals.",
            }

        return {
            "player_a": player_a,
            "player_b": player_b,
            "best_of": best_of,
            "total_games": total_games,
            "games_left": 0,
            "player_a_win_probability": 1.0 if current_a > current_b else 0.0,
            "player_b_win_probability": 1.0 if current_b > current_a else 0.0,
            "tie_probability": 0.0,
            "current_a_best": round(current_a, 1),
            "current_b_best": round(current_b, 1),
            "assumption": "No games remaining; outcome is based on current best-of totals.",
        }

    rng = np.random.default_rng(123)
    a_wins = 0.0
    b_wins = 0.0
    ties = 0.0

    for _ in range(simulations):
        sim_a = rng.normal(loc=a_mean, scale=a_std, size=games_left)
        sim_b = rng.normal(loc=b_mean, scale=b_std, size=games_left)

        sim_a = np.clip(sim_a, 0, 50)
        sim_b = np.clip(sim_b, 0, 50)

        final_a = best_score(a_vals + sim_a.tolist())
        final_b = best_score(b_vals + sim_b.tolist())

        if abs(final_a - final_b) < 1e-9:
            ties += 1
        elif final_a > final_b:
            a_wins += 1
        else:
            b_wins += 1

    return {
        "player_a": player_a,
        "player_b": player_b,
        "best_of": best_of,
        "total_games": total_games,
        "games_left": games_left,
        "player_a_win_probability": round(float(a_wins / simulations), 4),
        "player_b_win_probability": round(float(b_wins / simulations), 4),
        "tie_probability": round(float(ties / simulations), 4),
        "current_a_best": round(current_a, 1),
        "current_b_best": round(current_b, 1),
        "assumption": "Monte Carlo estimate using player IPS mean and variance from recorded rounds.",
    }
