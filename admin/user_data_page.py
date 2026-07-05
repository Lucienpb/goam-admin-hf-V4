import streamlit as st
import json
from pathlib import Path
from utils.github_storage import github_load_json, github_save_json

PLAYERS_FILE = Path("data/players.json")

FIELDS = ["name", "membership", "handicap_index", "team", "email", "Nick1", "Nick2", "Nick3", "Nick4"]


def _load_players():
    data, sha = github_load_json("data/players.json")
    return data or [], sha


def _save_players(players, sha):
    github_save_json("data/players.json", players, sha=sha, message="User Data update via admin page")
    PLAYERS_FILE.write_text(json.dumps(players, indent=2))


def show_user_data_page():
    st.title("👥 User Data (Players)")

    players, sha = _load_players()

    if not players:
        st.error("No players found.")
        return

    # Search
    search = st.text_input("🔍 Search by name, email or membership")
    filtered = [
        p for p in players
        if not search or any(
            search.lower() in str(p.get(f, "")).lower()
            for f in ["name", "email", "membership"]
        )
    ]

    st.markdown(f"**{len(filtered)} player(s) found**")
    st.markdown("---")

    updated_players = list(players)

    for i, player in enumerate(players):
        if player not in filtered:
            continue

        with st.expander(f"{player.get('name', 'Unknown')} — {player.get('email', 'no email')}"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("Name", value=player.get("name", ""), key=f"name_{i}")
                membership = st.text_input("Membership", value=player.get("membership", ""), key=f"mem_{i}")
                handicap_index = st.number_input("Handicap Index", value=float(player.get("handicap_index", 0)), step=0.1, key=f"hcp_{i}")
                team = st.text_input("Team", value=player.get("team", ""), key=f"team_{i}")
                email = st.text_input("Email", value=player.get("email", ""), key=f"email_{i}")

            with col2:
                nick1 = st.text_input("Nick1", value=player.get("Nick1", ""), key=f"nick1_{i}")
                nick2 = st.text_input("Nick2", value=player.get("Nick2", ""), key=f"nick2_{i}")
                nick3 = st.text_input("Nick3", value=player.get("Nick3", ""), key=f"nick3_{i}")
                nick4 = st.text_input("Nick4", value=player.get("Nick4", ""), key=f"nick4_{i}")

            if st.button("💾 Save", key=f"save_{i}"):
                updated_players[players.index(player)] = {
                    "name": name,
                    "membership": membership,
                    "handicap_index": handicap_index,
                    "team": team,
                    "email": email.strip().lower(),
                    "Nick1": nick1,
                    "Nick2": nick2,
                    "Nick3": nick3,
                    "Nick4": nick4,
                }
                _save_players(updated_players, sha)
                st.success(f"{name} saved successfully.")
                st.rerun()
