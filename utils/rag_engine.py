# utils/rag_engine.py
from pathlib import Path
from typing import List
import streamlit as st
import json

DATA_DIR = Path("data")


def load_json(path: Path):
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _load_goam_data() -> List[str]:
    """
    Convert your GOAM JSON structure into simple text chunks
    that the LLM can use as context.
    """

    chunks = []

    scores = load_json(DATA_DIR / "goam_scores.json")

    for month, data in scores.items():
        course = data.get("course")
        players = data.get("players", [])

        # Month summary
        chunks.append(
            f"In {month} at {course}, there were {len(players)} players."
        )

        # Player-level chunks
        for p in players:
            name = p.get("name")
            strokes = p.get("strokes")
            ips = p.get("ips")
            nett = p.get("nett")
            team = p.get("team")

            chunks.append(
                f"{name} played at {course} in {month} with strokes {strokes}, "
                f"IPS {ips}, nett {nett}, team {team}."
            )

        # Placements
        placements = data.get("placements", [])
        for place in placements:
            chunks.append(
                f"{place['name']} placed {place['position']} in {month} with IPS {place['ips']}."
            )

        # LIV totals
        liv = data.get("liv_totals", {})
        for team_name, total in liv.items():
            chunks.append(
                f"In {month}, team {team_name} had a LIV total of {total}."
            )

        # OX Nau
        ox = data.get("ox_nau")
        if ox:
            chunks.append(f"In {month}, the OX Nau was {ox}.")

    return chunks


@st.cache_resource
def load_chunks() -> List[str]:
    """Cache all GOAM text chunks."""
    return _load_goam_data()


def retrieve_context(query: str, top_k: int = 6) -> List[str]:
    """
    Simple keyword-based retrieval.
    No heavy dependencies. Works in Docker.
    """

    chunks = load_chunks()
    query_words = query.lower().split()

    scored = []
    for text in chunks:
        score = sum(1 for w in query_words if w in text.lower())
        if score > 0:
            scored.append((score, text))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [t for _, t in scored[:top_k]]
