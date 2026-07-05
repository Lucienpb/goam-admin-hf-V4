---
title: Goam Admin
emoji: ⛳
app_file: app.py
sdk: streamlit
sdk_version: 1.57.0
app_port: 8501
tags:
  - streamlit
pinned: false
short_description: Goam Admin
---

# GOAM Admin

GOAM Admin is a Streamlit application for managing GOAM player data, pairings, handicaps, scorecards, and season leaderboards.

## Main Features

- Pairing matrix with player lookup and heatmap
- 4-ball generation with guest players, carting/walking controls, and manual swaps or replacements
- Generated scorecard flow based on a reusable template stored in `data/scorecard_template.json`
- Editable generated scorecards in Scores -> Scorecards
- Publish generated monthly scorecards into `data/goam_scores.json`
- GOAM leaderboards and workbook export
- Admin data manager for courses, players, pairings, and GOAM scores
- GOAM AI chat integrations

## Project Entry Points

- Main app: `app.py`
- Secondary Streamlit example/dashboard: `src/streamlit_app.py`

Run the main app locally with:

```bash
streamlit run app.py
```

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional extra setup:

- `playwright` is required only if you use the handicap scraping flow in `utils/handicap_scraper.py`
- `llama-cpp-python` is required only if you use the local LLM helper in `utils/local_llm.py`

Install `llama-cpp-python` separately for local environments only (not recommended for Hugging Face Space builds):

```bash
pip install llama-cpp-python
```

If you use Playwright locally, install the browser runtime after installing the package:

```bash
playwright install
```

## Environment Variables

The app uses the following environment variables in supported flows:

- `GITHUB_TOKEN`: GitHub token for repository-backed JSON sync
- `GITHUB_REPO`: repository name used by the GitHub storage helpers
- `HF_TOKEN`: Hugging Face token used by the GOAM AI client

## Important Data Files

Core JSON data is stored under `data/`.

- `data/players.json`: player master data, teams, nicknames, handicap-related fields
- `data/pairings.json`: monthly pairing/fourball history
- `data/goam_scores.json`: published monthly GOAM scorecards used by leaderboards and scorecard views
- `data/scorecard_template.csv`: source CSV template for generated scorecards
- `data/scorecard_template.json`: JSON template read by the app for generated scorecards
- `data/generated_scorecard.json`: working generated scorecard from the 4-ball process before or after publishing

## Monthly Scorecard Workflow

The intended monthly workflow is:

1. Go to 4-Ball Generation and generate the month’s fourballs.
2. Make any manual adjustments such as swaps, replacements, or late withdrawals.
3. In Scorecard from Fourballs, enter the month key and course name.
4. Create and save the generated scorecard JSON.
5. Open Scores -> Scorecards.
6. Edit the generated scorecard, including player names, LIV team values, and score fields.
7. Publish the generated scorecard to `data/goam_scores.json` so it becomes part of the normal GOAM scorecard and leaderboard flow.

## Admin Data Imports

The admin data manager supports uploading and loading:

- course information
- players
- pairings
- GOAM score workbooks

These imports update the JSON files used by the app.

## Notes

- The Hugging Face Space uses `app.py` as the app entry point.
- Some features rely on local files being present in `data/`.
- The generated scorecard flow is designed to be reused every month rather than treated as a one-off export.
