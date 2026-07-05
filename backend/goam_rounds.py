#---------------------------------
# GOAM Rounds Data Structure
#   - Stores all rounds (loaded from JSON) in memory
#   - Tracks position history for position change calculations
#---------------------------------

import pandas as pd

class GOAMRounds:
    def __init__(self):
        self.rounds = []                 # list of round DataFrames
        self.position_history = {}       # {player: [pos1, pos2, pos3, ...]}
        self.position_change = {}        # {player: delta}

    def update_position_history(self, leaderboard_df):
        """
        Called every time the leaderboard is built.
        This leaderboard represents the latest round.
        """

        # Extract current round positions
        current_positions = {
            row["Name"]: int(row["Position"])
            for _, row in leaderboard_df.iterrows()
        }

        # Store positions per round
        for name, pos in current_positions.items():
            if name not in self.position_history:
                self.position_history[name] = []
            self.position_history[name].append(pos)

        # Compute movement (only if 2+ rounds exist)
        for name, history in self.position_history.items():
            if len(history) < 2:
                self.position_change[name] = None
            else:
                prev = history[-2]
                curr = history[-1]
                self.position_change[name] = prev - curr

    def get_position_change(self, name):
        return self.position_change.get(name)
        
    def get_all_rounds(self):
        """Return all stored rounds as a single DataFrame."""
        if not self.rounds:
            return pd.DataFrame()
        return pd.concat(self.rounds, ignore_index=True)
