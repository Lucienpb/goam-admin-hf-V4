# Data Folder

This folder contains the data files required by the GOAM Admin Dashboard.

## Files

- **Course_Information.csv/xlsx** - Course information with tee ratings, slopes, and par for handicap calculations
- **player_ids.xlsx** - Sample file with player membership numbers and CAP values for batch processing
- **Players.csv** - Player list with names and other player information

## Usage

The app automatically looks for `Course_Information` file (in CSV or Excel format) in this folder when the Handicap Scraper is loaded. If not found, you can upload it manually through the app interface.

The `player_ids.xlsx` is used as a template for batch processing handicap data.
