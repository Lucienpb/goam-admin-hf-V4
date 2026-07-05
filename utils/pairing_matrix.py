"""
Pairing Matrix Module - Handles golf pairings and matrix building
"""
import pandas as pd
from datetime import datetime
from itertools import combinations

# ================================================================================
# NAME NORMALISATION
# ================================================================================
NAME_MAP = {
    "Uncle John": "John B",
    "John": "John B",
    "John B": "John B",
    "Winston": "Winna",
    "Winna": "Winna",
    "Jessie": "Jessi",
    "Jessi": "Jessi"
}

def normalize_name(name):
    """Normalize player names according to NAME_MAP"""
    if not name or str(name).strip() == "":
        return None
    name = str(name).strip()
    return NAME_MAP.get(name, name)

# ================================================================================
# PARSE PAIRINGS
# ================================================================================
def parse_pairings(uploaded_file):
    """Parse pairings from CSV file"""
    df = pd.read_csv(uploaded_file, header=None)
    current_month = None
    current_month_num = datetime.now().month
    rounds = []

    for _, row in df.iterrows():
        first_cell = str(row[0]) if pd.notna(row[0]) else ""

        if "'" in first_cell and ":" in first_cell:
            try:
                month_str = first_cell.split("'")[0]
                month_num = datetime.strptime(month_str, "%b").month
                current_month = month_num
            except Exception:
                current_month = None
            continue

        if current_month and current_month > current_month_num:
            continue

        players = [
            normalize_name(x)
            for x in row
            if pd.notna(x) and normalize_name(x)
        ]
        if len(players) >= 2:
            rounds.append(players)

    return rounds

# ================================================================================
# BUILD MATRIX
# ================================================================================
def build_matrix(rounds):
    """Build pairing matrix from rounds data"""
    players = sorted({p for group in rounds for p in group})
    matrix = pd.DataFrame("", index=players, columns=players, dtype="string")

    for p in players:
        matrix.loc[p, p] = "-"

    for group in rounds:
        for a, b in combinations(group, 2):
            current = matrix.loc[a, b]
            matrix.loc[a, b] = "1" if current == "" else str(int(current) + 1)
            matrix.loc[b, a] = matrix.loc[a, b]

    return matrix
