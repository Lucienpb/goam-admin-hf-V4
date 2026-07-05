#-------------------------------------------------
# Pairing Matrix & Fourball App (JSON Version)
#-------------------------------------------------

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
from itertools import combinations
from pathlib import Path

from utils.json_utils import load_json, save_json
from utils.fourball_generator import generate_fourballs
from utils.name_utils import (
    normalize_name,
    build_alias_map,
    build_display_name_map
)
from utils.aggrid_helper import show_aggrid

# ---------------------------------------------------------
# NAME VALIDATION & MAPPING LAYER
# ---------------------------------------------------------
def validate_and_map_names(players_df, pairings_json, alias_map):
    warnings = []

    valid_players = {normalize_name(p, alias_map): p for p in players_df["name"]}

    cleaned_pairings = {}

    for month, data in pairings_json.items():
        cleaned_fourballs = []

        for fb in data["fourballs"]:
            cleaned_players = []
            for p in fb["players"]:
                np = normalize_name(p, alias_map)

                if np not in valid_players:
                    warnings.append(f"⚠️ '{p}' in {month} not found in players.json")

                cleaned_players.append(np)

            cleaned_fourballs.append({
                "fourball": fb["fourball"],
                "players": cleaned_players
            })

        cleaned_pairings[month] = {
            "course": data["course"],
            "fourballs": cleaned_fourballs
        }

    return cleaned_pairings, warnings


# ---------------------------------------------------------
# BUILD PAIRING MATRIX
# ---------------------------------------------------------
def build_pairing_matrix(pairings_json, players_df, alias_map):
    official_players = set(players_df["name"].apply(lambda x: normalize_name(x, alias_map)))

    pairing_players = set()
    for month, data in pairings_json.items():
        for fb in data["fourballs"]:
            for p in fb["players"]:
                pairing_players.add(normalize_name(p, alias_map))

    all_players = sorted(official_players.union(pairing_players))

    matrix = pd.DataFrame(0, index=all_players, columns=all_players, dtype=int)

    for month, data in pairings_json.items():
        for fb in data["fourballs"]:
            players = [normalize_name(p, alias_map) for p in fb["players"]]
            for a, b in combinations(players, 2):
                matrix.loc[a, b] += 1
                matrix.loc[b, a] += 1

    for p in all_players:
        matrix.loc[p, p] = 0

    return matrix


# ---------------------------------------------------------
# FORMAT PLAYER DISPLAY
# ---------------------------------------------------------
def format_player(p, display_map, teams, player_modes):
    nick = display_map.get(p, p)
    team = teams.get(p, "")
    mode = player_modes.get(p, "Walking 🚶‍♂️")
    icon = "🛺" if "Carting" in mode else "🚶‍♂️"
    team_part = f" ({team})" if team else ""
    return f"{nick}{team_part} {icon}"


def _build_fourball_rows(groups, display_map, teams, player_modes):
    rows = []
    for i, g in enumerate(groups, 1):
        row = {
            "Fourball": i,
            "Player 1": format_player(g[0], display_map, teams, player_modes) if len(g) > 0 else "",
            "Player 2": format_player(g[1], display_map, teams, player_modes) if len(g) > 1 else "",
            "Player 3": format_player(g[2], display_map, teams, player_modes) if len(g) > 2 else "",
            "Player 4": format_player(g[3], display_map, teams, player_modes) if len(g) > 3 else "",
        }
        rows.append(row)
    return rows


def _find_player_slot(groups, player):
    for gi, group in enumerate(groups):
        for pi, current in enumerate(group):
            if current == player:
                return gi, pi
    return None, None


def _load_scorecard_template_json():
    template_json_path = "data/scorecard_template.json"
    template_csv_path = Path("data/scorecard_template.csv")

    template_data = load_json(template_json_path)
    if isinstance(template_data, list) and template_data:
        return template_data

    if template_csv_path.exists():
        df_template = pd.read_csv(template_csv_path).fillna("")
        template_data = df_template.to_dict(orient="records")
        save_json(template_json_path, template_data)
        return template_data

    return []


def _default_scorecard_fields(template_rows):
    if not template_rows:
        return {
            "Strokes": "",
            "IPS": "",
            "LIV": "",
            "Handicap": "",
            "NP1": "",
            "NP2": "",
            "LD1": "",
            "LD2": "",
            "BG": "",
            "BN": "",
            "Pool Bet": "",
            "Pool Payouts": "",
            "Fines": "",
        }

    base = {}
    for col in template_rows[0].keys():
        if col != "Name":
            base[col] = ""
    return base


def _build_scorecard_from_fourballs(groups, template_rows, display_map, team_name_map):
    template_by_name = {
        str(row.get("Name", "")).strip().lower(): row
        for row in template_rows
        if str(row.get("Name", "")).strip()
    }
    default_fields = _default_scorecard_fields(template_rows)

    rows = []
    for i, group in enumerate(groups, 1):
        for player in group:
            name_key = str(player).strip().lower()
            template_row = template_by_name.get(name_key, {})
            display_name = display_map.get(player, player)

            row = {"Name": display_name}
            for field, default_val in default_fields.items():
                row[field] = template_row.get(field, default_val)
            row["LIV"] = team_name_map.get(player, row.get("LIV", ""))
            row["Fourball"] = i
            rows.append(row)

    return rows


# ---------------------------------------------------------
# MATRIX PAGE
# ---------------------------------------------------------
def show_matrix_page(players_df, pairings_json, alias_map, display_map):
    st.header("📊 Pairing Matrix")

    matrix = build_pairing_matrix(pairings_json, players_df, alias_map)

    # Mark unofficial players
    official_set = set(players_df["name"].apply(lambda x: normalize_name(x, alias_map)))
    for p in matrix.index:
        if p not in official_set:
            display_map[p] = f"{p}*"
        else:
            if p not in display_map:
                display_map[p] = p

    matrix_display = matrix.copy().astype(object)
    for p in matrix_display.index:
        matrix_display.loc[p, p] = "-"

    matrix_display.index = [display_map.get(p, p) for p in matrix.index]
    matrix_display.columns = [display_map.get(p, p) for p in matrix.columns]

    with st.expander("View Matrix", expanded=False):
        show_aggrid(matrix_display)

    # Heatmap
    show_heatmap = st.checkbox("Show pairing heatmap")

    if show_heatmap:
        st.subheader("🔥 Pairing Heatmap")

        numeric_matrix = matrix.astype(int)

        fig, ax = plt.subplots()
        im = ax.imshow(numeric_matrix.values, cmap="YlOrRd")

        ax.set_xticks(range(len(matrix.columns)))
        ax.set_yticks(range(len(matrix.index)))
        ax.set_xticklabels([display_map.get(p, p) for p in matrix.columns], rotation=90)
        ax.set_yticklabels([display_map.get(p, p) for p in matrix.index])

        plt.colorbar(im, ax=ax, label="Times paired")
        st.pyplot(fig)

    # Lookup
    st.subheader("🔍 Player Pairing Lookup")

    players_list = [p.strip() for p in matrix.index]

    lookup_player = st.selectbox(
        "Select a player",
        players_list,
        format_func=lambda p: display_map.get(p.strip(), p.strip())
    )

    if lookup_player:
        lookup_player = lookup_player.strip()

        played_with = []
        not_played_with = []

        for p in players_list:
            if p == lookup_player:
                continue

            val = matrix.loc[lookup_player, p]

            if int(val) > 0:
                played_with.append(p)
            else:
                not_played_with.append(p)

        with st.expander(
            f"✅ {display_map.get(lookup_player, lookup_player)} HAS played with ({len(played_with)})",
            expanded=False
        ):
            show_aggrid(pd.DataFrame({"Player": [display_map.get(p, p) for p in played_with]}))

        with st.expander(
            f"❌ {display_map.get(lookup_player, lookup_player)} has NOT played with ({len(not_played_with)})",
            expanded=False
        ):
            show_aggrid(pd.DataFrame({"Player": [display_map.get(p, p) for p in not_played_with]}))


# ---------------------------------------------------------
# FOURBALL GENERATOR PAGE
# ---------------------------------------------------------
def show_generator_page(players_df, pairings_json, alias_map, display_map):
    st.header("🏌️ 4‑Ball Generator")

    matrix = build_pairing_matrix(pairings_json, players_df, alias_map)
    matrix_players = list(matrix.index)
    template_rows = _load_scorecard_template_json()

    if "pairing_generated_groups" not in st.session_state:
        st.session_state["pairing_generated_groups"] = []
    if "pairing_generated_groups_original" not in st.session_state:
        st.session_state["pairing_generated_groups_original"] = []

    # Persist guest players across reruns so they remain in the selector.
    if "pairing_guest_players" not in st.session_state:
        st.session_state["pairing_guest_players"] = {}

    guest_players = st.session_state["pairing_guest_players"]

    for guest_id, guest_meta in guest_players.items():
        display_map[guest_id] = guest_meta.get("name", guest_id)

    all_players = matrix_players + [gid for gid in guest_players if gid not in matrix_players]

    if "pairing_selected_players" not in st.session_state:
        st.session_state["pairing_selected_players"] = all_players.copy()

    # ADD/CLEAR GUESTS BEFORE PLAYER SELECTOR
    # Streamlit forbids mutating a widget's key after the widget is instantiated.
    st.subheader("➕ Add Guest Players")

    guest_name = st.text_input("Guest name")
    guest_cart = st.checkbox("Guest is carting 🛺", value=False)

    if st.button("Add Guest"):
        name_clean = guest_name.strip()

        if name_clean:
            guest_id = "guest_" + name_clean.lower().replace(" ", "_")

            guest_players[guest_id] = {
                "name": name_clean,
                "carting": guest_cart,
            }
            st.session_state["pairing_guest_players"] = guest_players

            current_selected = st.session_state.get("pairing_selected_players", [])
            if guest_id not in current_selected:
                st.session_state["pairing_selected_players"] = current_selected + [guest_id]

            st.success(f"Guest added: {name_clean}")
            st.rerun()

    if st.button("Clear Guests"):
        st.session_state["pairing_guest_players"] = {}
        current_selected = st.session_state.get("pairing_selected_players", [])
        st.session_state["pairing_selected_players"] = [
            p for p in current_selected if not p.startswith("guest_")
        ]
        st.success("All guest players cleared.")
        st.rerun()

    # Recompute options after possible add/clear actions.
    guest_players = st.session_state["pairing_guest_players"]
    for guest_id, guest_meta in guest_players.items():
        display_map[guest_id] = guest_meta.get("name", guest_id)

    all_players = matrix_players + [gid for gid in guest_players if gid not in matrix_players]

    st.subheader("📝 Select Players Playing This Month")
    valid_defaults = [p for p in st.session_state["pairing_selected_players"] if p in all_players]
    selected_players = st.multiselect(
        "Choose players for this month",
        all_players,
        default=valid_defaults if valid_defaults else all_players,
        key="pairing_selected_players",
        format_func=lambda p: display_map.get(p, p)
    )

    st.caption(f"Players selected this month: {len(selected_players)}")

    team_name_map = dict(
        zip(
            players_df["name"].apply(lambda x: normalize_name(x, alias_map)),
            players_df["team"].fillna("")
        )
    )

    # TEAM INITIALS
    teams = dict(
        zip(
            players_df["name"].apply(lambda x: normalize_name(x, alias_map)),
            players_df["team"].apply(lambda t: "".join(word[0] for word in t.split()).upper())
        )
    )

    # PLAYER MODES
    player_modes = {
        gid: ("Carting 🛺" if meta.get("carting") else "Walking 🚶‍♂️")
        for gid, meta in guest_players.items()
    }
    for gid in guest_players:
        teams[gid] = ""
        team_name_map[gid] = ""

    # WALKING / CARTING TABLE
    st.subheader("🚶‍♂️ / 🛺 Walking or Carting")

    header_cols = st.columns([0.25, 1])
    with header_cols[0]:
        st.markdown("### Player")
    with header_cols[1]:
        st.markdown("### Carting")

    st.markdown("""
        <style>
            .big-checkbox .stCheckbox > label > div:first-child {
                transform: scale(1.5);
                margin-left: -8px;
                margin-top: 2px;
            }
        </style>
    """, unsafe_allow_html=True)

    eligible_cart_players = [p for p in selected_players if not p.startswith("guest_")]
    all_carting = bool(eligible_cart_players) and all(
        st.session_state.get(f"cart_{p}", False) for p in eligible_cart_players
    )

    carting_toggle_all = st.checkbox(
        "Select all carting 🛺",
        value=all_carting,
        help="Tick to mark all selected players as carting. Untick to mark all as walking.",
    )

    if eligible_cart_players and carting_toggle_all != all_carting:
        for p in eligible_cart_players:
            st.session_state[f"cart_{p}"] = carting_toggle_all
        st.rerun()

    for p in selected_players:
        if p.startswith("guest_"):
            continue

        c1, c2 = st.columns([0.25, 1])

        with c1:
            st.markdown(
                f"<div style='font-size:1.1rem; font-weight:600; margin-top:6px;'>{display_map.get(p, p)}</div>",
                unsafe_allow_html=True
            )

        with c2:
            st.markdown("<div class='big-checkbox'>", unsafe_allow_html=True)
            is_cart = st.checkbox("🛺", key=f"cart_{p}", label_visibility="visible")
            st.markdown("</div>", unsafe_allow_html=True)

        player_modes[p] = "Carting 🛺" if is_cart else "Walking 🚶‍♂️"

    strict_mode = st.checkbox("Strict mode (never allow 1- or 2-balls)", value=True)

    shuffle_seed = st.number_input(
        "Shuffle seed",
        min_value=0,
        value=0,
        step=1
    )

    if st.button("Generate Fourballs"):
        if len(selected_players) < 3:
            st.error("Need at least 3 players to generate fourballs.")
            return

        final_groups, penalty = generate_fourballs(
            selected_players,
            teams,
            matrix,
            strict_mode,
            shuffle_seed,
            player_modes
        )

        st.session_state["pairing_generated_groups"] = [list(g) for g in final_groups]
        st.session_state["pairing_generated_groups_original"] = [list(g) for g in final_groups]
        st.session_state["pairing_generated_scorecard_rows"] = []

    final_groups = st.session_state.get("pairing_generated_groups", [])

    if final_groups:
        st.subheader("🏌️ Fourballs for Next Month")

        rows = _build_fourball_rows(final_groups, display_map, teams, player_modes)
        show_aggrid(pd.DataFrame(rows))

        st.subheader("✏️ Manual Adjustments")
        st.caption("Swap players between fourballs or replace late withdrawals.")

        current_players = [p for g in final_groups for p in g]

        swap_col, replace_col = st.columns(2)

        with swap_col:
            st.markdown("**Swap players**")
            swap_a = st.selectbox(
                "Player A",
                current_players,
                key="swap_player_a",
                format_func=lambda p: display_map.get(p, p),
            )

            swap_b_options = [p for p in current_players if p != swap_a]
            swap_b = st.selectbox(
                "Player B",
                swap_b_options,
                key="swap_player_b",
                format_func=lambda p: display_map.get(p, p),
            ) if swap_b_options else None

            if st.button("Swap Players"):
                if not swap_a or not swap_b:
                    st.warning("Select two different players to swap.")
                else:
                    g1, p1 = _find_player_slot(final_groups, swap_a)
                    g2, p2 = _find_player_slot(final_groups, swap_b)

                    if g1 is None or g2 is None:
                        st.error("Could not locate one or both players in the current fourballs.")
                    else:
                        final_groups[g1][p1], final_groups[g2][p2] = final_groups[g2][p2], final_groups[g1][p1]
                        st.session_state["pairing_generated_groups"] = final_groups
                        st.success("Players swapped.")
                        st.rerun()

        with replace_col:
            st.markdown("**Replace withdrawn player**")
            withdrawn_player = st.selectbox(
                "Withdrawn player",
                current_players,
                key="withdrawn_player",
                format_func=lambda p: display_map.get(p, p),
            )

            replacement_pool = [p for p in all_players if p not in current_players]
            replacement_player = st.selectbox(
                "Replacement player",
                replacement_pool,
                key="replacement_player",
                format_func=lambda p: display_map.get(p, p),
            ) if replacement_pool else None

            if st.button("Replace Player"):
                if not withdrawn_player:
                    st.warning("Select the withdrawn player.")
                elif not replacement_player:
                    st.warning("No replacement players available. Add or select another player first.")
                else:
                    g, p = _find_player_slot(final_groups, withdrawn_player)
                    if g is None:
                        st.error("Withdrawn player not found in current fourballs.")
                    else:
                        final_groups[g][p] = replacement_player
                        st.session_state["pairing_generated_groups"] = final_groups
                        st.success("Player replaced.")
                        st.rerun()

        if st.button("Reset Manual Changes"):
            st.session_state["pairing_generated_groups"] = [
                list(g) for g in st.session_state.get("pairing_generated_groups_original", [])
            ]
            st.success("Manual changes reset to the generated fourballs.")
            st.rerun()

        st.subheader("🧾 Scorecard from Fourballs")
        if not template_rows:
            st.warning("No scorecard template found. Add data/scorecard_template.json or data/scorecard_template.csv.")
        else:
            month_key = st.text_input(
                "Month key (example: Jul'26)",
                value=st.session_state.get("pairing_scorecard_month_key", ""),
                key="pairing_scorecard_month_key",
            )
            course_name = st.text_input(
                "Course name",
                value=st.session_state.get("pairing_scorecard_course_name", ""),
                key="pairing_scorecard_course_name",
            )

            if st.button("Create Scorecard JSON"):
                scorecard_rows = _build_scorecard_from_fourballs(
                    final_groups,
                    template_rows,
                    display_map,
                    team_name_map,
                )
                st.session_state["pairing_generated_scorecard_rows"] = scorecard_rows

            scorecard_rows = st.session_state.get("pairing_generated_scorecard_rows", [])
            if scorecard_rows:
                st.dataframe(pd.DataFrame(scorecard_rows), hide_index=True, use_container_width=True)

                save_path = "data/generated_scorecard.json"
                json_payload = {
                    "month_key": month_key,
                    "course": course_name,
                    "scorecard": scorecard_rows
                }

                st.download_button(
                    label="Download generated scorecard JSON",
                    data=json.dumps(json_payload, indent=2),
                    file_name="generated_scorecard.json",
                    mime="application/json",
                    use_container_width=True,
                )

                if st.button("Save generated scorecard to data/generated_scorecard.json"):
                    save_json(save_path, json_payload)
                    st.success("Saved generated scorecard to data/generated_scorecard.json")


# ---------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------
def run(mode="matrix"):
    players = load_json("data/players.json")
    raw_pairings = load_json("data/pairings.json")

    if not players:
        st.error("No players found.")
        return

    if not raw_pairings:
        st.error("No pairings found.")
        return

    players_df = pd.DataFrame(players)

    alias_map = build_alias_map(players_df)
    display_map = build_display_name_map(players_df)

    pairings_json, warnings = validate_and_map_names(players_df, raw_pairings, alias_map)

    # mismatches hidden

    if mode == "matrix":
        show_matrix_page(players_df, pairings_json, alias_map, display_map)

    elif mode == "generator":
        show_generator_page(players_df, pairings_json, alias_map, display_map)

    else:
        st.error("Invalid mode for pairing_app.run()")
