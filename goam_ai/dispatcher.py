from goam_ai.actions import (
    summarize_player,
    summarize_team,
    summarize_course,
    compare_players,
    compare_trends,
    plot_trajectory,
    predict_next,
)
from goam_ai.actions.player_monthly_scores import player_monthly_scores
from goam_ai.actions.estimate_league_chances import estimate_league_chances
from goam_ai.actions.estimate_head_to_head_chances import estimate_head_to_head_chances
from goam_ai.actions.estimate_team_league_chances import estimate_team_league_chances
from goam_ai.actions.season_insights import season_insights
from goam_ai.actions.player_trends import player_trends

def dispatch(df, instruction: dict):
    action = instruction.get("action")

    # --------------------------------------------------------
    # IDENTITY HANDLER
    # --------------------------------------------------------
    if action == "identity":
        player = instruction.get("player")
        if player == "Goami":
            return {"text": "I am Goami, your GOAM golf analytics assistant!"}
        elif player:
            return {"text": f"You are {player}."}
        else:
            return {"text": "I could not match your login to a GOAM player."}

    # --------------------------------------------------------
    # PLAYER SUMMARY
    # --------------------------------------------------------
    if action == "summarize_player":
        return summarize_player(
            df=df,
            player=instruction.get("player", "")
        )
    
    # --------------------------------------------------------
    # PLAYER MONTHLY SCORES (for tables)
    # --------------------------------------------------------
    if action == "player_monthly_scores":
        return player_monthly_scores(
            df=df,
            player=instruction.get("player", "")
        )

    # --------------------------------------------------------
    # TEAM SUMMARY
    # --------------------------------------------------------
    if action == "summarize_team":
        return summarize_team(
            df=df,
            team=instruction.get("team", "")
        )

    # --------------------------------------------------------
    # SEASON INSIGHTS
    # --------------------------------------------------------
    if action == "season_insights":
        return season_insights(df=df)

    # --------------------------------------------------------
    # PLAYER TRENDS
    # --------------------------------------------------------
    if action == "player_trends":
        return player_trends(df=df, min_rounds=4)

    # --------------------------------------------------------
    # COURSE SUMMARY
    # --------------------------------------------------------
    if action == "summarize_course":
        return summarize_course(
            df=df,
            course=instruction.get("course", "")
        )

    # --------------------------------------------------------
    # COMPARE PLAYERS
    # --------------------------------------------------------
    if action == "compare_players":
        return compare_players(
            df=df,
            players=instruction.get("players", []),
            metric=instruction.get("metric", "ips"),
        )

    # --------------------------------------------------------
    # COMPARE TRENDS
    # --------------------------------------------------------
    if action == "compare_trends":
        return compare_trends(
            df=df,
            players=instruction.get("players", []),
            metric=instruction.get("metric", "ips"),
            window=instruction.get("window", 3),
        )

    # --------------------------------------------------------
    # TRAJECTORY
    # --------------------------------------------------------
    if action == "plot_trajectory":
        return plot_trajectory(
            df=df,
            player=instruction.get("player", ""),
            metric=instruction.get("metric", "ips"),
            rounds=instruction.get("rounds"),
        )

    # --------------------------------------------------------
    # PREDICT NEXT ROUND
    # --------------------------------------------------------
    if action == "predict_next":
        return predict_next(
            df=df,
            player=instruction.get("player", ""),
            metric=instruction.get("metric", "ips"),
            window=instruction.get("window", 3),
        )

    # --------------------------------------------------------
    # LEAGUE WIN CHANCES
    # --------------------------------------------------------
    if action == "league_chances":
        return estimate_league_chances(
            df=df,
            player=instruction.get("player", ""),
            games_left=instruction.get("games_left", 2),
            simulations=instruction.get("simulations", 3000),
        )

    # --------------------------------------------------------
    # TEAM LEAGUE WIN CHANCES
    # --------------------------------------------------------
    if action == "team_league_chances":
        return estimate_team_league_chances(
            df=df,
            team=instruction.get("team", ""),
            games_left=instruction.get("games_left", 2),
            simulations=instruction.get("simulations", 3000),
        )

    # --------------------------------------------------------
    # HEAD-TO-HEAD LEAGUE CHANCES
    # --------------------------------------------------------
    if action == "head_to_head_chances":
        players = instruction.get("players", [])
        if len(players) < 2:
            return {"error": "head_to_head_chances requires 2 players"}
        return estimate_head_to_head_chances(
            df=df,
            player_a=players[0],
            player_b=players[1],
            best_of=instruction.get("best_of", 6),
            total_games=instruction.get("total_games", 8),
            simulations=instruction.get("simulations", 3000),
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------
    return {"error": f"Unknown action: {action}"}
