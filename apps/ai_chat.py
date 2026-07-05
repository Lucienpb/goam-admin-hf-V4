import streamlit as st
import pandas as pd
import textwrap
import os
import json
import time
from datetime import datetime
from pathlib import Path

from utils.rag_engine import retrieve_context
from goam_ai.query_parser import parse_query_with_fallback
from goam_ai.dispatcher import dispatch
from goam_ai.llm_client import call_llm, choose_model_id
from goam_ai.config import load_ai_config
from goam_ai.evaluation import run_regression_suite
from backend.goam_loader import GOAMLoader
from backend.goam_calculator import GOAMCalculator


SYSTEM_PROMPT = """
You are GOAM Assistant, a friendly golf analytics expert.
You answer using:
1) The user's real GOAM data (action_result)
2) The retrieved context (RAG)
3) Simple, clear English

GOLF SCORING RULES:
- IPS (Index Performance Score): HIGHER is BETTER. If you have 35 IPS and someone has 30 IPS, you performed better.
- Strokes: LOWER is BETTER. If you scored 90 strokes and someone scored 95, you performed better.
- Nett: LOWER is BETTER (adjusted for handicap).

COMPARISON LOGIC:
- If Player A has avg IPS of 33 and Player B has 27, then Player A performs BETTER than Player B.
- If Player A has avg strokes of 95 and Player B has 92, then Player B performs BETTER than Player A.

Rules:
- Never invent numbers.
- Always explain IPS, strokes, nett in simple terms.
- If action_result contains an error, explain it politely.
- When comparing players, use correct golf logic (higher IPS = better, lower strokes = better).
"""


def _zero_cost_mode_enabled() -> bool:
    cfg = load_ai_config()
    default = "1" if bool(cfg.get("zero_cost_mode", True)) else "0"
    return os.getenv("GOAM_AI_ZERO_COST", default).strip().lower() in {"1", "true", "yes", "on"}


def _format_zero_cost_answer(instruction: dict, action_result: dict) -> str:
    action = instruction.get("action", "unknown")
    confidence = float(instruction.get("_parse_confidence", 0.0) or 0.0)

    if not isinstance(action_result, dict):
        return f"I completed action '{action}', but the result format is unexpected."

    if action_result.get("error"):
        return _format_missing_data_answer(action, action_result.get("error", "Unknown error"), instruction)

    if action_result.get("text"):
        return str(action_result.get("text"))

    if action == "summarize_player":
        return (
            f"{action_result.get('player', instruction.get('player', 'Player'))} has played "
            f"{int(action_result.get('rounds', 0))} rounds. "
            f"Average IPS is {float(action_result.get('avg_ips', 0.0)):.1f}, with best IPS "
            f"{float(action_result.get('best_ips', 0.0)):.1f} and worst IPS {float(action_result.get('worst_ips', 0.0)):.1f}. "
            f"Average strokes: {float(action_result.get('avg_strokes', 0.0)):.1f} "
            f"(best {int(action_result.get('best_strokes', 0))}, worst {int(action_result.get('worst_strokes', 0))})."
        )

    if action == "player_monthly_scores":
        rows = action_result.get("monthly_scores", [])
        if not rows:
            return "No monthly scores were found for that player."
        lines = [
            f"{r.get('month', '-')}: {r.get('course', '-')} | IPS {r.get('ips', '-')} | Strokes {r.get('strokes', '-')}"
            for r in rows
        ]
        return (
            f"Monthly scores for {action_result.get('player', instruction.get('player', 'player'))}:\n"
            + "\n".join(lines)
            + f"\n\nSummary: {int(action_result.get('total_rounds', 0))} rounds, avg IPS {float(action_result.get('avg_ips', 0.0)):.1f}."
        )

    if action == "summarize_team":
        players = action_result.get("players", [])
        player_text = ", ".join(players[:8]) + ("..." if len(players) > 8 else "")
        return (
            f"Team {action_result.get('team', instruction.get('team', '-'))} has {len(players)} active players "
            f"across {int(action_result.get('rounds', 0))} recorded rounds. "
            f"Avg IPS {float(action_result.get('avg_ips', 0.0)):.1f}, best {float(action_result.get('best_ips', 0.0)):.1f}, "
            f"avg strokes {float(action_result.get('avg_strokes', 0.0)):.1f}."
            + (f"\nPlayers: {player_text}" if player_text else "")
        )

    if action == "summarize_course":
        return (
            f"At {action_result.get('course', instruction.get('course', '-'))}, there are "
            f"{int(action_result.get('rounds', 0))} recorded rounds. "
            f"Field avg IPS is {float(action_result.get('avg_ips', 0.0)):.1f} "
            f"(best {float(action_result.get('best_ips', 0.0)):.1f}, worst {float(action_result.get('worst_ips', 0.0)):.1f}). "
            f"Avg strokes is {float(action_result.get('avg_strokes', 0.0)):.1f}."
        )

    if action == "season_insights":
        team_rows = action_result.get("team_standings", [])
        top_team = action_result.get("top_team", {})
        consistent = action_result.get("most_consistent_player", {})
        challengers = action_result.get("challengers", [])
        participation = action_result.get("participation_leaders", [])
        high_avg_low_rounds = action_result.get("high_avg_low_rounds")
        best_single = action_result.get("best_single_round", {})
        tight_gap = action_result.get("tight_mid_pack_gap")

        standings_line = ", ".join(
            f"{r.get('team')}: {float(r.get('course_points', 0) or 0):.0f}" for r in team_rows[:5]
        )
        challenger_lines = [
            f"- {c.get('player')}: {float(c.get('total_ips', 0) or 0):.0f} points, average {float(c.get('avg_ips', 0) or 0):.1f}"
            for c in challengers
        ]
        participation_lines = [
            f"- {p.get('player')}: {float(p.get('total_ips', 0) or 0):.0f} points over {int(p.get('rounds', 0) or 0)} events"
            for p in participation[:3]
        ]

        insight_1 = (
            f"1. {top_team.get('team', 'Top team')} are the current team leaders\n"
            f"The LIV standings currently show {standings_line}. "
            f"Gap between 1st and 2nd is {float(top_team.get('gap_to_second', 0) or 0):.1f} points."
        )
        insight_2 = (
            f"2. {consistent.get('player', 'Top player')} is the strongest all-round individual performer\n"
            f"They have {float(consistent.get('total_ips', 0) or 0):.0f} total IPS at an average of "
            f"{float(consistent.get('avg_ips', 0) or 0):.1f} over {int(consistent.get('rounds', 0) or 0)} events."
        )
        insight_3 = (
            "3. Participation is a major leaderboard advantage\n"
            "Players with more events are converting consistency into higher totals:\n"
            + "\n".join(participation_lines)
        )
        if high_avg_low_rounds:
            insight_3 += (
                f"\nA high-average player with fewer events is {high_avg_low_rounds.get('player')} "
                f"(avg {float(high_avg_low_rounds.get('avg_ips', 0) or 0):.1f}, "
                f"{float(high_avg_low_rounds.get('total_ips', 0) or 0):.0f} points over "
                f"{int(high_avg_low_rounds.get('rounds', 0) or 0)} events)."
            )

        additional = [
            f"- Highest single IPS round: {best_single.get('player', '-')} scored {float(best_single.get('ips', 0) or 0):.0f} at {best_single.get('course', '-')}."
        ]
        if tight_gap is not None:
            additional.append(
                f"- Mid-pack LIV battle is tight: only {float(tight_gap):.1f} points separate 2nd and 4th place."
            )
        additional.extend(challenger_lines)

        return (
            f"I analyzed {action_result.get('dataset_label', 'current GOAM data')} "
            f"({int(action_result.get('events_total', 0) or 0)} events, {int(action_result.get('rounds_total', 0) or 0)} player-rounds).\n\n"
            "🏁 Top 3 Insights\n"
            f"{insight_1}\n\n"
            f"{insight_2}\n"
            + ("\n" + "\n".join(challenger_lines) if challenger_lines else "")
            + "\n\n"
            f"{insight_3}\n\n"
            "🔎 Additional Findings\n"
            + "\n".join(additional)
            + "\n\n🧭 Questions for deeper analysis\n"
            "1. Player performance trends - who is improving or declining over time?\n"
            "2. Team analytics - which players contribute the most to each team's success?\n"
            "3. Course analysis - which courses are hardest/easiest based on scoring?\n"
            "4. Consistency rankings - who is most reliable round-to-round?\n"
            "5. Projected season outcomes - who is on pace to win if current trends continue?"
        )

    if action == "player_trends":
        events = action_result.get("events", [])
        hottest = action_result.get("hottest", [])
        dipping = action_result.get("dipping", [])
        consistent = action_result.get("consistent", [])
        power = action_result.get("power_ranking", [])
        best_single = action_result.get("best_single_round", {})

        def _series_text(row):
            series = row.get("ips_series", [])
            if not series:
                return ""
            return " -> ".join(str(int(v)) for v in series[-6:])

        hot_lines = []
        hot_positive_count = 0
        for row in hottest:
            if float(row.get("momentum", 0) or 0) > 0:
                hot_positive_count += 1
            hot_lines.append(
                f"{row.get('player')} is carrying solid form with IPS scores of {_series_text(row)}. "
                f"Average IPS is {float(row.get('avg_ips', 0) or 0):.1f}, and recent momentum is "
                f"{float(row.get('momentum', 0) or 0):+.1f}. [1]"
            )

        dip_lines = []
        for row in dipping:
            dip_lines.append(
                f"{row.get('player')} has cooled off across {_series_text(row)}. "
                f"Average IPS is {float(row.get('avg_ips', 0) or 0):.1f} with momentum at "
                f"{float(row.get('momentum', 0) or 0):+.1f}. [1]"
            )

        consistent_lines = []
        for row in consistent:
            consistent_lines.append(
                f"{row.get('player')} has delivered a stable run of {_series_text(row)} with a low variability proxy "
                f"(std {float(row.get('volatility', 0) or 0):.1f}). [1]"
            )

        power_lines = []
        for idx, row in enumerate(power, start=1):
            power_lines.append(
                f"{idx}. {row.get('player')} - recent avg {float(row.get('recent_avg', 0) or 0):.1f}, momentum {float(row.get('momentum', 0) or 0):+.1f}"
            )

        summary_hot = hottest[0].get("player") if hottest else "Top in-form player"
        summary_consistent = consistent[0].get("player") if consistent else "most reliable player"

        if summary_hot == summary_consistent:
            takeaway = (
                f"The latest form read points to {summary_hot} as both the current in-form benchmark and the most reliable performer week-to-week. "
            )
        else:
            takeaway = (
                f"The latest form read points to {summary_hot} as the current in-form benchmark, while {summary_consistent} remains the most reliable performer week-to-week. "
            )

        return (
            "Player Performance Trends\n"
            f"Using IPS scores across recorded events ({' -> '.join(events)}), several clear form patterns emerge. [1]\n\n"
            + ("📈 Strongest Positive Momentum\n" if hot_positive_count > 0 else "📊 Best Current Momentum (no net positive swing in this window)\n")
            + ("\n".join(hot_lines) if hot_lines else "No momentum signals found.")
            + "\n\n📉 Players Experiencing a Dip\n"
            + ("\n".join(dip_lines) if dip_lines else "No clear dip trend found.")
            + "\n\n🎯 Most Consistent Performers\n"
            + ("\n".join(consistent_lines) if consistent_lines else "No consistency signals found.")
            + "\n\n🏆 Trend-Based Power Ranking\n"
            + ("\n".join(power_lines) if power_lines else "No ranking available.")
            + "\n\nKey Takeaway\n"
            + takeaway
            + f"Highest single round in this analyzed set: {best_single.get('player', '-')} with {best_single.get('ips', '-')} IPS. [1]"
        )

    if action == "compare_players":
        stats = action_result.get("players", [])
        metric = action_result.get("metric", "ips")
        if not stats:
            return "I could not find stats for the requested players."
        reverse = metric == "ips"
        ranked = sorted(stats, key=lambda s: float(s.get("avg", 0) or 0), reverse=reverse)
        lines = []
        for idx, s in enumerate(ranked, start=1):
            short_name = str(s.get("name", "")).split()[0] or str(s.get("name", "Player"))
            lines.append(f"{idx}. {short_name} ({float(s.get('avg', 0) or 0):.1f})")
        return "\n".join(lines)

    if action == "compare_trends":
        players = action_result.get("players", instruction.get("players", []))
        p1 = players[0] if len(players) > 0 else "Player 1"
        p2 = players[1] if len(players) > 1 else "Player 2"
        return (
            f"Trend comparison over last {int(action_result.get('window', 3))} rounds (IPS): "
            f"{p1} = {float(action_result.get('p1_trend', 0.0)):.1f}, "
            f"{p2} = {float(action_result.get('p2_trend', 0.0)):.1f}. "
            f"Difference: {float(action_result.get('trend_diff', 0.0)):.1f}."
        )

    if action == "plot_trajectory":
        months = action_result.get("months", [])
        values = action_result.get("values", [])
        paired = [f"{m}: {v}" for m, v in zip(months, values)]
        if not paired:
            return "No trajectory values found for that player."
        return (
            f"Trajectory for {action_result.get('player', instruction.get('player', '-'))} "
            f"({action_result.get('metric', 'ips').upper()}):\n" + "\n".join(paired)
        )

    if action == "predict_next":
        return (
            f"Predicted next {action_result.get('metric', 'ips').upper()} for "
            f"{action_result.get('player', instruction.get('player', '-'))}: "
            f"{float(action_result.get('predicted_next', 0.0)):.1f} "
            f"(based on last {int(action_result.get('window', 3))} rounds)."
        )

    if action == "league_chances":
        win_pct = float(action_result.get("win_probability", 0.0)) * 100.0
        podium_pct = float(action_result.get("podium_probability", 0.0)) * 100.0
        return (
            f"Estimated chance of winning the IPS league for {action_result.get('player', instruction.get('player', '-'))} "
            f"with {int(action_result.get('games_left', 2))} games left is {win_pct:.1f}%. "
            f"Top-3 chance is {podium_pct:.1f}%.\n"
            f"Current rank: {action_result.get('current_rank', '-')}, "
            f"Best6 IPS: {action_result.get('current_best6_ips', '-')}, "
            f"gap to leader ({action_result.get('leader', '-')}) is {action_result.get('gap_to_leader', '-')}.\n"
            f"Method: {action_result.get('assumption', 'simulation estimate')}"
        )

    if action == "team_league_chances":
        win_pct = float(action_result.get("win_probability", 0.0)) * 100.0
        podium_pct = float(action_result.get("podium_probability", 0.0)) * 100.0
        return (
            f"Estimated chance of {action_result.get('team', instruction.get('team', '-'))} winning the LIV league "
            f"with {int(action_result.get('games_left', 2))} games left is {win_pct:.1f}%. "
            f"Top-3 chance is {podium_pct:.1f}%.\n"
            f"Current rank: {action_result.get('current_rank', '-')}, "
            f"Total points: {action_result.get('current_total', '-')}, "
            f"gap to leader ({action_result.get('leader', '-')}) is {action_result.get('gap_to_leader', '-')}.\n"
            f"Method: {action_result.get('assumption', 'simulation estimate')}"
        )

    if action == "head_to_head_chances":
        a = action_result.get("player_a", "Player A")
        b = action_result.get("player_b", "Player B")
        a_pct = float(action_result.get("player_a_win_probability", 0.0)) * 100.0
        b_pct = float(action_result.get("player_b_win_probability", 0.0)) * 100.0
        tie_pct = float(action_result.get("tie_probability", 0.0)) * 100.0
        return (
            f"Head-to-head IPS league estimate ({a} vs {b}) with best {int(action_result.get('best_of', 6))} "
            f"from {int(action_result.get('total_games', 8))} games:\n"
            f"- {a} finishing ahead: {a_pct:.1f}%\n"
            f"- {b} finishing ahead: {b_pct:.1f}%\n"
            f"- Tie: {tie_pct:.1f}%\n"
            f"Games left: {int(action_result.get('games_left', 0))}. "
            f"Current best scores: {a} {action_result.get('current_a_best', '-')}, "
            f"{b} {action_result.get('current_b_best', '-')}.\n"
            f"Method: {action_result.get('assumption', 'simulation estimate')}"
        )

    fallback = json.dumps(action_result, indent=2, default=str)
    if confidence < 0.4:
        return (
            "I am not fully confident I interpreted your question correctly. "
            "Try naming a player/team/course explicitly.\n\n"
            f"Raw result:\n{fallback}"
        )
    return fallback


def _format_missing_data_answer(action: str, error_text: str, instruction: dict) -> str:
    base = f"I could not complete '{action}': {error_text}."

    if action in {"summarize_player", "player_monthly_scores", "plot_trajectory", "predict_next", "league_chances"}:
        player = instruction.get("player")
        suffix = f" Player requested: {player}." if player else ""
        return base + suffix + " Please confirm the player name as stored in GOAM."

    if action in {"team_league_chances"}:
        team = instruction.get("team")
        suffix = f" Team requested: {team}." if team else ""
        return base + suffix + " Please use the exact team name from the LIV leaderboard."

    if action in {"season_insights"}:
        return base + " Please ensure GOAM scores are loaded with player, team, course and IPS values."

    if action in {"player_trends"}:
        return base + " Please ensure enough player history exists (at least 4 rounds per player) for trend analysis."

    if action in {"head_to_head_chances", "compare_players", "compare_trends"}:
        players = instruction.get("players", [])
        return base + f" Players requested: {players}. Please provide 2 valid player names."

    if action in {"summarize_team"}:
        team = instruction.get("team")
        suffix = f" Team requested: {team}." if team else ""
        return base + suffix + " Please use the exact team name from the leaderboard."

    if action in {"summarize_course"}:
        course = instruction.get("course")
        suffix = f" Course requested: {course}." if course else ""
        return base + suffix + " Please use the exact course name from GOAM scores."

    return base


def _format_unknown_action_answer(question: str) -> str:
    return (
        "I could not confidently map that question to a GOAM analytics action. "
        "Try one of these patterns:\n"
        "- Summarize player <name>\n"
        "- Compare <player1> vs <player2>\n"
        "- Show monthly scores for <name>\n"
        "- Summarize team <team>\n"
        "- Summarize course <course>\n\n"
        "- Analyze this season and give top insights\n\n"
        "- Player performance trends\n\n"
        "- What are my chances of winning the league with 2 games left\n\n"
        "- What are Home Boys chances of winning the LIV league\n\n"
        "- What are the chances of Ashley beating me in the league, best of 6 for 8 games\n\n"
        f"Your question was: {question}"
    )


def _parser_fallback_enabled() -> bool:
    cfg = load_ai_config()
    default = "1" if bool(cfg.get("parser_fallback_enabled", True)) else "0"
    return os.getenv("GOAM_AI_PARSER_FALLBACK", default).strip().lower() in {"1", "true", "yes", "on"}


def _log_interaction(entry: dict):
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "ai_interactions.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def _read_interaction_logs(max_rows: int = 500):
    path = Path("logs") / "ai_interactions.jsonl"
    if not path.exists():
        return []

    records = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        records.append(row)
                except Exception:
                    continue
    except Exception:
        return []

    return records[-max_rows:]


def _show_phase21_diagnostics():
    with st.expander("📈 AI Diagnostics (Phase 2.1)", expanded=False):
        logs = _read_interaction_logs(max_rows=1000)
        if not logs:
            st.info("No AI interaction logs yet. Ask a question to generate diagnostics data.")
            return

        today_utc = datetime.utcnow().date()
        cfg = load_ai_config()
        threshold = st.slider(
            "Low-confidence threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(cfg.get("low_confidence_threshold", 0.60)),
            step=0.05,
        )

        rows = []
        for row in logs:
            ts_raw = str(row.get("timestamp", "")).replace("Z", "")
            try:
                ts = datetime.fromisoformat(ts_raw)
                is_today = ts.date() == today_utc
                ts_display = ts.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                is_today = False
                ts_display = str(row.get("timestamp", ""))

            confidence = float(row.get("parse_confidence", 0.0) or 0.0)
            if not is_today or confidence >= threshold:
                continue

            rows.append(
                {
                    "time_utc": ts_display,
                    "confidence": round(confidence, 2),
                    "source": row.get("parse_source", "unknown"),
                    "action": row.get("action", "unknown"),
                    "has_error": bool(row.get("has_error", False)),
                    "latency_ms": int(row.get("latency_ms", 0) or 0),
                    "question": str(row.get("question", ""))[:180],
                }
            )

        c1, c2, c3 = st.columns(3)
        c1.metric("Total logged", len(logs))
        c2.metric("Today low-confidence", len(rows))
        avg_conf = round(sum(float(r.get("confidence", 0.0)) for r in rows) / len(rows), 2) if rows else 0.0
        c3.metric("Avg confidence", avg_conf)

        if not rows:
            st.success("No low-confidence queries found for today at this threshold.")
            return

        diag_df = pd.DataFrame(rows).sort_values(by=["confidence", "time_utc"], ascending=[True, False])
        st.dataframe(diag_df, hide_index=True, use_container_width=True)
        st.caption("Use this table to identify unclear prompts and add parser rules or aliases.")


def _save_latest_regression(result: dict):
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "ai_eval_latest.json"
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_latest_regression():
    path = Path("logs") / "ai_eval_latest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _show_phase3_quality_governance(df, logged_in_player):
    cfg = load_ai_config()
    min_pass_rate = float(cfg.get("min_regression_pass_rate", 0.85))

    with st.expander("🛡️ AI Quality Gate (Phase 3)", expanded=False):
        latest = _load_latest_regression()
        if latest:
            pass_rate = float(latest.get("pass_rate", 0.0) or 0.0)
            st.caption(f"Latest regression run: {latest.get('timestamp', 'unknown')}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Pass rate", f"{pass_rate * 100:.1f}%")
            c2.metric("Passed", int(latest.get("passed_cases", 0) or 0))
            c3.metric("Total", int(latest.get("total_cases", 0) or 0))

            if pass_rate < min_pass_rate:
                st.error(
                    f"Deploy gate failed: pass rate {pass_rate * 100:.1f}% is below threshold {min_pass_rate * 100:.1f}%"
                )
            else:
                st.success(
                    f"Deploy gate passed: pass rate {pass_rate * 100:.1f}% meets threshold {min_pass_rate * 100:.1f}%"
                )

            rows = latest.get("rows", [])
            if isinstance(rows, list) and rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No regression suite run found yet.")

        if st.button("Run Regression Suite", use_container_width=True, key="run_ai_regression_suite"):
            result = run_regression_suite(df, logged_in_player=logged_in_player)
            _save_latest_regression(result)
            st.rerun()

def build_answer_prompt(question: str, context_chunks: list[str], action_result: dict | None) -> str:
    context_block = "\n".join(context_chunks)

    action_block = ""
    if action_result:
        action_block = f"\nAction result:\n{action_result}\n"

    return textwrap.dedent(f"""
        {SYSTEM_PROMPT}

        Context:
        {context_block}

        {action_block}

        Question:
        {question}

        Answer:
    """)


def run():
    st.header("🤖 GOAM AI Chat (Hugging Face API)")
    zero_cost_mode = _zero_cost_mode_enabled()
    parser_fallback_enabled = _parser_fallback_enabled()
    if zero_cost_mode:
        st.caption("AI Mode: Zero-cost deterministic mode (no paid model calls)")
    elif parser_fallback_enabled:
        st.caption("AI Mode: Tiered model routing + parser fallback enabled")

    _show_phase21_diagnostics()

    # Chat history
    if "goam_chat" not in st.session_state:
        st.session_state.goam_chat = []

    # Get logged-in player from session state (set during login)
    logged_in_player = st.session_state.get("player_name")
    
    if not logged_in_player:
        st.warning("Player name not found in session. Please login again.")
        return

    # Load scores DataFrame from GOAM data
    try:
        goam_scores = GOAMLoader.load_json_scores("data/goam_scores.json")
        df = GOAMCalculator.build_from_json(goam_scores)
        
        if df is None or df.empty:
            st.error("No GOAM scores found. Please load data via the Data Manager.")
            return
        
        # Rename columns to match dispatcher expectations (lowercase)
        df = df.rename(columns={
            "Name": "player",
            "Strokes": "strokes",
            "IPS": "ips",
            "Course": "course",
            "Team": "team",
            "Month": "month",
        })
    except Exception as e:
        st.error(f"Error loading GOAM scores: {e}")
        return

    # Re-render quality gate with live dataframe context.
    _show_phase3_quality_governance(df=df, logged_in_player=logged_in_player)

    # Display chat history
    for role, msg in st.session_state.goam_chat:
        if role == "user":
            st.markdown(f"**You:** {msg}")
        else:
            st.markdown(f"**GOAM Assistant:** {msg}")

    st.markdown("---")

    question = st.text_input("Ask anything about your GOAM stats…")
    if st.button("Ask") and question.strip():
        started = time.perf_counter()
        st.session_state.goam_chat.append(("user", question))

        with st.spinner("Thinking…"):
            # 1) Convert question → structured action
            # Build lists for the parser

            players_list = sorted(df["player"].dropna().unique().tolist())
            teams_list = sorted(df["team"].dropna().unique().tolist())
            courses_list = sorted(df["course"].dropna().unique().tolist())
            
            # Parse the question
            instruction = parse_query_with_fallback(
                question,
                players_list=players_list,
                teams_list=teams_list,
                courses_list=courses_list,
                logged_in_player=logged_in_player,
                enable_llm_fallback=(not zero_cost_mode and parser_fallback_enabled),
            )

            # 2) Run the action on your real GOAM data
            if instruction.get("action") == "unknown":
                action_result = {"error": "Unknown intent"}
                answer = _format_unknown_action_answer(question)
            else:
                action_result = dispatch(df, instruction)

                # 3) Short-circuit: if action_result has a direct text, use it
                if "text" in action_result:
                    answer = action_result["text"]
                elif zero_cost_mode:
                    answer = _format_zero_cost_answer(instruction, action_result)
                else:
                    # 4) Retrieve RAG context
                    context = retrieve_context(question)

                    # 5) Build final LLM prompt
                    prompt = build_answer_prompt(question, context, action_result)

                    # 6) Generate natural language answer
                    try:
                        answer = call_llm(
                            prompt,
                            max_new_tokens=400,
                            temperature=0.3,
                            action=instruction.get("action"),
                        )
                    except Exception:
                        # Safety fallback if model call fails.
                        answer = _format_zero_cost_answer(instruction, action_result)

            latency_ms = int((time.perf_counter() - started) * 1000)
            _log_interaction(
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "question": question,
                    "instruction": instruction,
                    "action": instruction.get("action"),
                    "zero_cost_mode": zero_cost_mode,
                    "parser_fallback_enabled": parser_fallback_enabled,
                    "parse_source": instruction.get("_parse_source", "unknown"),
                    "parse_confidence": float(instruction.get("_parse_confidence", 0.0) or 0.0),
                    "model_used": None if zero_cost_mode else choose_model_id(instruction.get("action")),
                    "has_error": bool(isinstance(action_result, dict) and action_result.get("error")),
                    "latency_ms": latency_ms,
                }
            )

        # Save assistant response
        st.session_state.goam_chat.append(("assistant", answer))

        # DEBUG: Show dispatcher output
        st.divider()
        with st.expander("🔍 Debug Info - Dispatcher Output"):
            st.json({
                "instruction": instruction,
                "action_result": action_result
            })
        st.divider()

    # Optional: show trajectory chart if last action returned data
    if st.session_state.goam_chat:
        last_action = st.session_state.goam_chat[-1][1]
