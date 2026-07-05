"""
Login Page for GOAM Admin
Includes:
- Email + password login
- Account lockout after failed attempts
- Throttle file tracking
- Verified email enforcement
"""

import streamlit as st
import json
import os
import time
from datetime import datetime
from pathlib import Path

from auth.auth import load_users, verify_password, USERS_FILE, get_player_name_from_email

from utils.github_storage import load_all_app_data

from goam_ai.data_loader import json_to_df

# ========================================================================
# THROTTLE / LOCKOUT SETTINGS
# ========================================================================

THROTTLE_FILE = "auth/login_throttle.json"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes


# ========================================================================
# INTERNAL HELPERS
# ========================================================================

def _ensure_throttle_file():
    if not os.path.exists(THROTTLE_FILE):
        with open(THROTTLE_FILE, "w") as f:
            json.dump({}, f)


def get_login_attempts(email):
    _ensure_throttle_file()
    with open(THROTTLE_FILE, "r") as f:
        data = json.load(f)
    return data.get(email, {"failed": 0, "last_fail": 0})


def record_failed_attempt(email):
    _ensure_throttle_file()
    with open(THROTTLE_FILE, "r") as f:
        data = json.load(f)

    entry = data.get(email, {"failed": 0, "last_fail": 0})
    entry["failed"] += 1
    entry["last_fail"] = int(time.time())

    data[email] = entry
    with open(THROTTLE_FILE, "w") as f:
        json.dump(data, f)


def record_successful_login(email):
    _ensure_throttle_file()
    with open(THROTTLE_FILE, "r") as f:
        data = json.load(f)

    if email in data:
        del data[email]

    with open(THROTTLE_FILE, "w") as f:
        json.dump(data, f)


def is_account_locked(email):
    entry = get_login_attempts(email)
    if entry["failed"] < MAX_FAILED_ATTEMPTS:
        return False

    elapsed = int(time.time()) - entry["last_fail"]
    return elapsed < LOCKOUT_DURATION


def get_lockout_remaining_seconds(email):
    entry = get_login_attempts(email)
    elapsed = int(time.time()) - entry["last_fail"]
    remaining = LOCKOUT_DURATION - elapsed
    return max(0, remaining)


# ========================================================================
# LOGIN PAGE UI
# ========================================================================

def show_login_page():
    st.title("🔐 GOAM Admin Login")
    st.write("Welcome back. Please sign in to continue.")

    email = st.text_input("Email Address", width=500)
    password = st.text_input("Password", type="password", width=500)

    login_btn = st.button("Login", width=100)

    if not login_btn:
        return

    users = load_users()

    # Normalize email for lookup
    email_norm = email.strip().lower()

    # --- VALIDATION ---
    if not email or not password:
        st.error("Please enter both email and password")
        return

    if email_norm not in users:
        st.error("No account found with that email")
        st.info(f"Using users.json at: {Path(USERS_FILE).resolve()}")
        return

    # --- LOCKOUT CHECK ---
    if is_account_locked(email_norm):
        remaining = get_lockout_remaining_seconds(email_norm)
        st.error(f"Too many failed attempts. Try again in {remaining} seconds.")
        return

    user = users[email_norm]

    # --- EMAIL VERIFIED? ---
    if not user.get("verified", False):
        st.warning("Your email is not verified yet.")
        st.info("Please check your inbox for the verification link.")
        return

    # --- PASSWORD CHECK ---
    if not verify_password(password, user["password_hash"]):
        record_failed_attempt(email_norm)
        attempts = get_login_attempts(email_norm)["failed"]

        if attempts >= MAX_FAILED_ATTEMPTS:
            st.error("Account locked due to too many failed attempts.")
        else:
            st.error(f"Incorrect password. Attempts: {attempts}/{MAX_FAILED_ATTEMPTS}")

        return

    # --- SUCCESS ---
    record_successful_login(email_norm)
    
    st.success("Login successful!")
    
    # Load GitHub data (your existing code stays unchanged)
    
    # ------------------------------------------------------------
    # FINAL SUCCESS BLOCK — SET SESSION STATE
    # ------------------------------------------------------------
    st.session_state.authenticated = True
    st.session_state.email = email_norm
    st.session_state.role = user.get("role", "member")
    st.session_state.login_time = datetime.now()
    
    # Get player name for AI Chat (from players.json or user.json)
    player_name = get_player_name_from_email(email_norm)
    st.session_state["player_name"] = player_name
    
    st.rerun()


