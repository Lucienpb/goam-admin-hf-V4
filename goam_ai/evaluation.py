from datetime import datetime

from goam_ai.query_parser import parse_query_with_fallback
from goam_ai.dispatcher import dispatch


def _build_default_cases(df, logged_in_player=None):
    players = sorted(df["player"].dropna().unique().tolist())
    teams = sorted(df["team"].dropna().unique().tolist())
    courses = sorted(df["course"].dropna().unique().tolist())

    cases = []

    if players:
        cases.append(
            {
                "name": "player_summary",
                "query": f"Summarize player {players[0]}",
                "expected_action": "summarize_player",
            }
        )

    if len(players) >= 2:
        cases.append(
            {
                "name": "compare_players",
                "query": f"Compare {players[0]} vs {players[1]}",
                "expected_action": "compare_players",
            }
        )

    if teams:
        cases.append(
            {
                "name": "team_summary",
                "query": f"Summarize team {teams[0]}",
                "expected_action": "summarize_team",
            }
        )

    if courses:
        cases.append(
            {
                "name": "course_summary",
                "query": f"Summarize course {courses[0]}",
                "expected_action": "summarize_course",
            }
        )

    cases.append(
        {
            "name": "season_insights",
            "query": "Analyze this season and give top insights",
            "expected_action": "season_insights",
        }
    )

    cases.append(
        {
            "name": "player_trends",
            "query": "Player performance trends",
            "expected_action": "player_trends",
        }
    )

    cases.append(
        {
            "name": "unknown_guard",
            "query": "Tell me something random about oceans",
            "expected_action": "unknown",
        }
    )

    if logged_in_player:
        cases.append(
            {
                "name": "identity_logged_in",
                "query": "Who am I?",
                "expected_action": "identity",
            }
        )

    return cases


def run_regression_suite(df, logged_in_player=None):
    players_list = sorted(df["player"].dropna().unique().tolist())
    teams_list = sorted(df["team"].dropna().unique().tolist())
    courses_list = sorted(df["course"].dropna().unique().tolist())

    cases = _build_default_cases(df, logged_in_player=logged_in_player)
    rows = []

    for case in cases:
        query = case["query"]
        expected_action = case["expected_action"]

        instruction = parse_query_with_fallback(
            query,
            players_list=players_list,
            teams_list=teams_list,
            courses_list=courses_list,
            logged_in_player=logged_in_player,
            enable_llm_fallback=False,
        )

        actual_action = instruction.get("action", "unknown")
        action_match = actual_action == expected_action

        if actual_action == "unknown":
            action_result = {"error": "Unknown intent"}
            no_error = expected_action == "unknown"
        else:
            action_result = dispatch(df, instruction)
            no_error = not (isinstance(action_result, dict) and action_result.get("error"))

        passed = bool(action_match and no_error)

        rows.append(
            {
                "case": case["name"],
                "query": query,
                "expected_action": expected_action,
                "actual_action": actual_action,
                "parse_confidence": float(instruction.get("_parse_confidence", 0.0) or 0.0),
                "parse_source": instruction.get("_parse_source", "unknown"),
                "no_error": no_error,
                "passed": passed,
            }
        )

    total = len(rows)
    passed_count = sum(1 for r in rows if r["passed"])
    pass_rate = (passed_count / total) if total else 0.0

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_cases": total,
        "passed_cases": passed_count,
        "pass_rate": round(pass_rate, 4),
        "rows": rows,
    }
