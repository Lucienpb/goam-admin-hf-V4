import re
import json
from pathlib import Path

from goam_ai.llm_client import call_llm

BASE_DIR = Path(__file__).parent.parent
PLAYERS_FILE = BASE_DIR / "data" / "players.json"

def _load_nicknames():
    """Load player nicknames from players.json"""
    try:
        if not PLAYERS_FILE.exists():
            return {}
        
        players_data = json.loads(PLAYERS_FILE.read_text())
        nickname_map = {}  # nickname -> full name
        
        for player in players_data:
            full_name = player.get("name", "")
            for i in range(1, 5):
                nick = player.get(f"Nick{i}", "").strip()
                if nick:
                    nickname_map[nick.lower()] = full_name
        
        return nickname_map
    except Exception:
        return {}

NICKNAME_MAP = _load_nicknames()

ALLOWED_ACTIONS = {
    "identity",
    "summarize_player",
    "player_monthly_scores",
    "summarize_team",
    "summarize_course",
    "season_insights",
    "player_trends",
    "compare_players",
    "compare_trends",
    "plot_trajectory",
    "predict_next",
    "league_chances",
    "team_league_chances",
    "head_to_head_chances",
    "unknown",
}


def _safe_json_object(text: str):
    if not text:
        return None

    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _validate_instruction(candidate, players_list, teams_list, courses_list, logged_in_player=None):
    if not isinstance(candidate, dict):
        return None

    action = str(candidate.get("action", "unknown")).strip()
    if action not in ALLOWED_ACTIONS:
        return None

    def in_players(name):
        return isinstance(name, str) and name in players_list

    def in_teams(team):
        return isinstance(team, str) and team in teams_list

    def in_courses(course):
        return isinstance(course, str) and course in courses_list

    if action == "identity":
        player = candidate.get("player")
        if player in ("Goami", logged_in_player) or player is None:
            return {"action": "identity", "player": player}
        return None

    if action in {"summarize_player", "player_monthly_scores", "plot_trajectory", "predict_next", "league_chances"}:
        player = candidate.get("player")
        if not in_players(player):
            return None
        payload = {"action": action, "player": player}
        if action in {"plot_trajectory", "predict_next"}:
            payload["metric"] = "ips"
            window = candidate.get("window", 3)
            try:
                payload["window"] = max(2, min(12, int(window)))
            except Exception:
                payload["window"] = 3
        if action == "league_chances":
            games_left = candidate.get("games_left", 2)
            simulations = candidate.get("simulations", 3000)
            try:
                payload["games_left"] = max(1, min(12, int(games_left)))
            except Exception:
                payload["games_left"] = 2
            try:
                payload["simulations"] = max(500, min(10000, int(simulations)))
            except Exception:
                payload["simulations"] = 3000
        return payload

    if action == "team_league_chances":
        team = candidate.get("team")
        if not in_teams(team):
            return None
        games_left = candidate.get("games_left", 2)
        simulations = candidate.get("simulations", 3000)
        try:
            games_left = max(1, min(12, int(games_left)))
        except Exception:
            games_left = 2
        try:
            simulations = max(500, min(10000, int(simulations)))
        except Exception:
            simulations = 3000
        return {
            "action": "team_league_chances",
            "team": team,
            "games_left": games_left,
            "simulations": simulations,
        }

    if action == "summarize_team":
        team = candidate.get("team")
        if not in_teams(team):
            return None
        return {"action": action, "team": team}

    if action == "summarize_course":
        course = candidate.get("course")
        if not in_courses(course):
            return None
        return {"action": action, "course": course}

    if action == "season_insights":
        return {"action": "season_insights"}

    if action == "player_trends":
        return {"action": "player_trends"}

    if action in {"compare_players", "compare_trends"}:
        players = candidate.get("players")
        if not isinstance(players, list):
            return None
        players = [p for p in players if in_players(p)]
        players = list(dict.fromkeys(players))
        if len(players) < 2:
            return None
        metric = str(candidate.get("metric", "ips")).strip().lower()
        if metric not in {"ips", "strokes"}:
            metric = "ips"
        payload = {
            "action": action,
            "players": players,
            "metric": metric,
        }
        if action == "compare_trends":
            payload["metric"] = "ips"
            window = candidate.get("window", 3)
            try:
                payload["window"] = max(2, min(12, int(window)))
            except Exception:
                payload["window"] = 3
        return payload

    if action == "head_to_head_chances":
        players = candidate.get("players")
        if not isinstance(players, list):
            return None
        players = [p for p in players if in_players(p)]
        players = list(dict.fromkeys(players))
        if len(players) < 2:
            return None

        best_of = candidate.get("best_of", 6)
        total_games = candidate.get("total_games", 8)
        simulations = candidate.get("simulations", 3000)

        try:
            best_of = max(1, min(12, int(best_of)))
        except Exception:
            best_of = 6
        try:
            total_games = max(best_of, min(20, int(total_games)))
        except Exception:
            total_games = 8
        try:
            simulations = max(500, min(10000, int(simulations)))
        except Exception:
            simulations = 3000

        return {
            "action": "head_to_head_chances",
            "players": players[:2],
            "best_of": best_of,
            "total_games": total_games,
            "simulations": simulations,
        }

    if action == "unknown":
        return {"action": "unknown", "query": str(candidate.get("query", "")).strip()}

    return None


def _build_fallback_prompt(question, players_list, teams_list, courses_list, logged_in_player=None):
    players_block = "\n".join(f"- {p}" for p in players_list)
    teams_block = "\n".join(f"- {t}" for t in teams_list)
    courses_block = "\n".join(f"- {c}" for c in courses_list)

    me_hint = logged_in_player or "None"

    return f"""
You are a strict query router for a golf analytics app.
Return ONLY valid JSON (no markdown, no commentary).

Allowed actions:
- identity (fields: player)
- summarize_player (fields: player)
- player_monthly_scores (fields: player)
- summarize_team (fields: team)
- summarize_course (fields: course)
- season_insights (fields: none)
- player_trends (fields: none)
- compare_players (fields: players, metric)
- compare_trends (fields: players, metric, window)
- plot_trajectory (fields: player, metric)
- predict_next (fields: player, metric, window)
- league_chances (fields: player, games_left, simulations)
- team_league_chances (fields: team, games_left, simulations)
- head_to_head_chances (fields: players, best_of, total_games, simulations)
- unknown (fields: query)

Rules:
- metric must be "ips" or "strokes" when present
- players list must contain >= 2 names for compare actions
- use only names from allowed lists below
- for broad season analysis or top insights requests, use season_insights
- for player trend/momentum/form requests, use player_trends
- if unsure, return unknown

Logged in player (for pronouns like me/my/i): {me_hint}

Allowed players:
{players_block}

Allowed teams:
{teams_block}

Allowed courses:
{courses_block}

User question:
{question}
""".strip()


def try_llm_parse_query(question, players_list, teams_list, courses_list, logged_in_player=None):
    prompt = _build_fallback_prompt(
        question,
        players_list,
        teams_list,
        courses_list,
        logged_in_player=logged_in_player,
    )

    response = call_llm(
        prompt=prompt,
        max_new_tokens=220,
        temperature=0.0,
        action="query_router",
    )

    candidate = _safe_json_object(response)
    return _validate_instruction(candidate, players_list, teams_list, courses_list, logged_in_player=logged_in_player)

def parse_query(question: str, players_list, teams_list, courses_list, logged_in_player=None):
    """
    Final GOAM AI Query Parser
    - Detects identity questions
    - Detects player, team, course references
    - Routes to correct action
    - Avoids accidental compare_trends triggers
    """

    q = question.lower().strip()

    # ------------------------------------------------------------
    # 1. IDENTITY HANDLER
    # ------------------------------------------------------------
    if any(x in q for x in ["who are you", "what is your name", "your name"]):
        return {
            "action": "identity",
            "player": "Goami"
        }

    if any(x in q for x in ["who am i", "my name", "who is me", "what is my name"]):
        return {
            "action": "identity",
            "player": logged_in_player
        }

    # ------------------------------------------------------------
    # 2. PLAYER DETECTION
    # ------------------------------------------------------------
    matched_players = []

    # Pronouns → logged-in player
    if logged_in_player:
        if any(x in q.split() for x in ["me", "my", "i", "myself"]):
            matched_players.append(logged_in_player)
    # Explicit player name detection
    for p in players_list:
        # full match
        if p.lower() in q:
            matched_players.append(p)
            continue

        # partial match (first name, last name) — whole word only
        tokens = p.lower().split()
        if any(re.search(rf"\b{re.escape(t)}\b", q) for t in tokens):
            matched_players.append(p)
    
    # Check nicknames in question
    for nick, full_name in NICKNAME_MAP.items():
        if re.search(rf"\b{re.escape(nick)}\b", q) and full_name in players_list:
            matched_players.append(full_name)

    matched_players = list(dict.fromkeys(matched_players))  # dedupe

    # ------------------------------------------------------------
    # 3. TEAM DETECTION
    # ------------------------------------------------------------
    matched_team = None
    for t in teams_list:
        if t.lower() in q:
            matched_team = t
            break

    # ------------------------------------------------------------
    # 4. COURSE DETECTION
    # ------------------------------------------------------------
    matched_course = None
    for c in courses_list:
        if c.lower() in q:
            matched_course = c
            break

    # ------------------------------------------------------------
    # 5. ACTION ROUTING
    # ------------------------------------------------------------

    league_keywords = [
        "chances of winning",
        "chance of winning",
        "winning the league",
        "winning the liv league",
        "win the league",
        "win the liv league",
        "odds of winning",
        "league chance",
        "liv league",
    ]
    asks_league = any(k in q for k in league_keywords)

    games_left = 2
    match = re.search(r"(\d+)\s*(games|game|rounds|round)\s*(left|remaining)", q)
    if match:
        try:
            games_left = max(1, min(12, int(match.group(1))))
        except Exception:
            games_left = 2

    if asks_league and matched_team:
        return {
            "action": "team_league_chances",
            "team": matched_team,
            "games_left": games_left,
            "simulations": 3000,
        }

    # SEASON INSIGHTS
    season_keywords = [
        "analyze",
        "analysis",
        "top insights",
        "big picture",
        "overall insights",
        "season outlook",
        "what stands out",
        "key findings",
    ]
    if any(k in q for k in season_keywords) and len(matched_players) == 0 and not matched_team and not matched_course:
        return {"action": "season_insights"}

    trend_keywords = [
        "player performance trends",
        "player trends",
        "trend analysis",
        "who is improving",
        "who is declining",
        "momentum",
        "in form",
        "power ranking",
        "most consistent",
    ]
    if any(k in q for k in trend_keywords):
        return {"action": "player_trends"}

    # COMPARE PLAYERS
    if ("compare" in q or "vs" in q or "versus" in q or "better" in q or "between" in q) and len(matched_players) >= 2:
        metric = "ips"
        if any(x in q for x in ["strokes", "stroke", "gross", "shot", "shots"]):
            metric = "strokes"
        return {
            "action": "compare_players",
            "players": matched_players,
            "metric": metric
        }

    # COMPARE TRENDS
    if "trend" in q and len(matched_players) == 2:
        return {
            "action": "compare_trends",
            "players": matched_players,
            "metric": "ips",
            "window": 3
        }

    # TRAJECTORY
    if any(x in q for x in ["trajectory", "progress", "improving", "history"]) and len(matched_players) == 1:
        return {
            "action": "plot_trajectory",
            "player": matched_players[0],
            "metric": "ips"
        }

    # PREDICT NEXT
    if any(x in q for x in ["predict", "next round", "next score"]) and len(matched_players) == 1:
        return {
            "action": "predict_next",
            "player": matched_players[0],
            "metric": "ips"
        }

    # LEAGUE CHANCES
    if asks_league and len(matched_players) == 1:
        return {
            "action": "league_chances",
            "player": matched_players[0],
            "games_left": games_left,
            "simulations": 3000,
        }

    # TEAM SUMMARY
    if matched_team and "compare" not in q:
        return {
            "action": "summarize_team",
            "team": matched_team
        }

    # COURSE SUMMARY
    if matched_course and "compare" not in q:
        return {
            "action": "summarize_course",
            "course": matched_course
        }

    # HEAD-TO-HEAD LEAGUE CHANCES
    h2h_keywords = ["chances of", "chance of", "odds of"]
    if len(matched_players) >= 2 and any(k in q for k in h2h_keywords) and any(x in q for x in ["beating", "beat", "finish above", "ahead of"]):
        best_of = 6
        total_games = 8

        best_match = re.search(r"best\s*of\s*(\d+)", q)
        if best_match:
            try:
                best_of = max(1, min(12, int(best_match.group(1))))
            except Exception:
                best_of = 6

        total_match = re.search(r"(?:for|out of|across)\s*(\d+)\s*(?:games|rounds)", q)
        if total_match:
            try:
                total_games = max(best_of, min(20, int(total_match.group(1))))
            except Exception:
                total_games = 8

        return {
            "action": "head_to_head_chances",
            "players": matched_players[:2],
            "best_of": best_of,
            "total_games": total_games,
            "simulations": 3000,
        }

    # PLAYER MONTHLY SCORES (for tables/full year data)
    if any(x in q for x in ["table", "scores", "all my", "entire year", "breakdown", "each round"]) and len(matched_players) == 1:
        return {
            "action": "player_monthly_scores",
            "player": matched_players[0]
        }

    # PLAYER SUMMARY
    if len(matched_players) == 1:
        return {
            "action": "summarize_player",
            "player": matched_players[0]
        }

    # ------------------------------------------------------------
    # 6. FALLBACK
    # ------------------------------------------------------------
    return {
        "action": "unknown",
        "query": question
    }


def parse_query_with_fallback(
    question: str,
    players_list,
    teams_list,
    courses_list,
    logged_in_player=None,
    enable_llm_fallback=False,
):
    primary = parse_query(
        question,
        players_list=players_list,
        teams_list=teams_list,
        courses_list=courses_list,
        logged_in_player=logged_in_player,
    )

    def with_meta(payload, source, confidence):
        if not isinstance(payload, dict):
            payload = {"action": "unknown", "query": question}
        out = dict(payload)
        out["_parse_source"] = source
        out["_parse_confidence"] = float(confidence)
        return out

    if primary.get("action") != "unknown":
        return with_meta(primary, "rules", 0.95)

    if not enable_llm_fallback:
        return with_meta(primary, "rules", 0.2)

    try:
        secondary = try_llm_parse_query(
            question,
            players_list=players_list,
            teams_list=teams_list,
            courses_list=courses_list,
            logged_in_player=logged_in_player,
        )
        if secondary:
            return with_meta(secondary, "llm_fallback", 0.72)
    except Exception:
        pass

    return with_meta(primary, "rules", 0.2)
