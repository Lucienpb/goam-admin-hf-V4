#---------------------------------
# GOAM Loader
#   - Loads GOAM Excel workbooks and single-round scorecards.
#   - Loads GOAM scores from JSON for Scores App
#---------------------------------

import pandas as pd

class GOAMLoader:
    """
    Loads GOAM Excel workbooks and single-round scorecards.
    """

    @staticmethod
    def load_season(file):
        """
        Load all sheets from a full-season workbook.
        Returns a dict: {sheet_name: DataFrame}
        """
        return pd.read_excel(file, sheet_name=None)

    @staticmethod
    def load_single_round(file):
        """
        Load a single-round scorecard.
        Must contain: Name, Strokes, IPS
        """
        df = pd.read_excel(file)
        required = {"Name", "Strokes", "IPS"}

        if not required.issubset(df.columns):
            raise ValueError(f"Scorecard missing required columns: {required}")

        return df
    @staticmethod
    def load_json_scores(path):
        import json
        with open(path, "r") as f:
            return json.load(f)
