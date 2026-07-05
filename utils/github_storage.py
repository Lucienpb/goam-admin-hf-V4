import os
import json
import base64
import requests
import streamlit as st

# ------------------------------------------------------------
# GitHub Repo Configuration
# ------------------------------------------------------------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # e.g. "Lucienpb/goam-admin-hf-v2"
GITHUB_BRANCH = "main"
USE_GITHUB = bool(GITHUB_TOKEN and GITHUB_REPO)




# ------------------------------------------------------------
# Internal helper: GitHub API request
# ------------------------------------------------------------
def _github_request(method, url, **kwargs):
    if not USE_GITHUB:
        raise RuntimeError("GitHub sync not configured. Set GITHUB_TOKEN and GITHUB_REPO.")

    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    headers["Accept"] = "application/vnd.github+json"

    response = requests.request(method, url, headers=headers, **kwargs)

    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub API error {response.status_code}: {response.text}"
        )

    return response.json()


# ------------------------------------------------------------
# Load JSON file from GitHub
# ALWAYS returns SHA, even if JSON is invalid
# ------------------------------------------------------------
def github_load_json(path):
    """
    Loads a JSON file from GitHub.
    Returns (data, sha).
    If JSON is invalid, returns ({}, sha).
    If file does not exist (404), returns (None, None).
    Any other error is raised.
    """
    if not USE_GITHUB:
        if not os.path.exists(path):
            return None, None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), None
        except Exception:
            return {}, None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"

    try:
        data = _github_request("GET", url)
    except RuntimeError as e:
        msg = str(e)

        # True "file not found"
        if "404" in msg:
            return None, None

        # Any other error should NOT be treated as missing file
        raise

    sha = data.get("sha")

    # Decode JSON safely
    try:
        decoded = base64.b64decode(data["content"]).decode("utf-8")
        json_data = json.loads(decoded)
        return json_data, sha
    except Exception:
        # File exists but JSON is corrupted — return empty dict but KEEP SHA
        return {}, sha

# ------------------------------------------------------------
# Save JSON file to GitHub
# Automatically handles create vs update
# ------------------------------------------------------------
def github_save_json(path, obj, sha=None, message=None):
    """
    Saves a JSON file to GitHub.
    If sha is provided → update.
    If sha is None → create.
    """
    if not USE_GITHUB:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        return True

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

    content_str = json.dumps(obj, indent=2)
    encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    if message is None:
        message = f"Update {path}"

    payload = {
        "message": message,
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }

    if sha:
        payload["sha"] = sha

    _github_request("PUT", url, json=payload)
    return True


# ============================================================
# HIGH-LEVEL APP HELPERS
# ============================================================

# ------------------------------------------------------------
# Load ALL app data after login
# ------------------------------------------------------------
def load_all_app_data():
    files = [
        "data/course_data.json",
        "data/goam_scores.json",
        "data/pairings.json",
        "data/players.json",
        "data/users.json",
    ]

    loaded = {}

    for f in files:
        data, sha = github_load_json(f)
        loaded[f] = {"data": data, "sha": sha}

    return loaded


# ------------------------------------------------------------
# Save JSON from Data Manager (Excel upload)
# ------------------------------------------------------------
def save_json_with_sha(path, new_data):
    _, sha = github_load_json(path)

    github_save_json(
        path,
        new_data,
        sha=sha,
        message=f"Data Manager update for {path}"
    )

    return True


# ------------------------------------------------------------
# Save a single user's updated record
# ------------------------------------------------------------
def save_user_record(username, updated_record):
    path = "data/users.json"

    users, sha = github_load_json(path)

    if users is None:
        users = {}

    if not isinstance(users, dict):
        users = {}

    users[username] = updated_record

    github_save_json(
        path,
        users,
        sha=sha,
        message=f"Update user {username} via profile page"
    )

    return True

# ------------------------------------------------------------
# Sync ALL app data from GitHub into local files
# ------------------------------------------------------------
def sync_all_from_github():
    if not USE_GITHUB:
        return

    files = [
        "data/users.json",
        "data/ai_config.json",
        "data/course_data.json",
        "data/goam_scores.json",
        "data/goam_rounds.json",
        "data/pairings.json",
        "data/players.json",
    ]

    for path in files:
        data, sha = github_load_json(path)
        if data is not None:
            # overwrite local file with latest GitHub data
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
