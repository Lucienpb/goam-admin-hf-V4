#---------------------------------
# GOAM Name Normalization Utils 
#   - Build alias map from players.json
#   - Normalize input names to official names
#---------------------------------

import re

def build_alias_map(players_df):
    """
    Build a dynamic alias map from players.json.
    Maps all nicknames and variations to the player's official name.
    """
    alias_map = {}

    for _, row in players_df.iterrows():
        official = row["name"].strip()

        # Map official name → official name
        alias_map[official.lower()] = official

        # Map last name alone
        last = official.split()[-1].lower()
        alias_map[last] = official

        # Map nickname columns
        for col in ["Nick1", "Nick2", "Nick3", "Nick4"]:
            if col in row and isinstance(row[col], str) and row[col].strip():
                alias = row[col].strip().lower()
                alias_map[alias] = official

    return alias_map


def build_display_name_map(players_df):
    """
    Display name = Nick1 if exists, else official name.
    """
    display_map = {}

    for _, row in players_df.iterrows():
        official = row["name"].strip()
        nick1 = row.get("Nick1")

        if isinstance(nick1, str) and nick1.strip():
            display_map[official] = nick1.strip()
        else:
            display_map[official] = official

    return display_map


def normalize_name(name, alias_map):
    """
    Normalize any input name to the official name.
    """
    if not isinstance(name, str):
        return name

    cleaned = re.sub(r"\s+", " ", name.strip()).lower()

    if cleaned in alias_map:
        return alias_map[cleaned]

    return name.title()
