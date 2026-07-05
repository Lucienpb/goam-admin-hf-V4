"""
Secure Authentication Module for Streamlit
Handles user authentication, email verification, password reset, and audit logging
"""

import json
import re
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Tuple
import bcrypt


# ========================================================================
# CONFIGURATION
# ========================================================================
BASE_DIR = Path(__file__).parent.parent
USERS_FILE = BASE_DIR / "data" / "user.json"
PLAYERS_FILE = BASE_DIR / "data" / "players.json"
AUDIT_LOG_FILE = BASE_DIR / "logs" / "auth_audit.log"
TOKEN_STORE_FILE = BASE_DIR / "data" / "tokens.json"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your-email@gmail.com"
SENDER_PASSWORD = "your-app-password"

EMAIL_VERIFICATION_TOKEN_EXPIRY = 24 * 60 * 60
PASSWORD_RESET_TOKEN_EXPIRY = 1 * 60 * 60

AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(AUDIT_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ========================================================================
# EMAIL NORMALIZATION
# ========================================================================

def normalize_email(email: str) -> str:
    return email.strip().lower()

# ========================================================================
# EMAIL VALIDATION
# ========================================================================

def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

# ========================================================================
# PLAYER NAME MAPPING (email → player name from players.json)
# ========================================================================

def get_player_name_from_email(email: str) -> Optional[str]:
    """
    Map email to player name from players.json by matching user info.
    Falls back to user.json name field if available.
    Returns None if no player found.
    """
    email_norm = normalize_email(email)
    
    # First, check if user.json has a name field
    users = load_users_raw()
    if email_norm in users and users[email_norm].get("name"):
        return users[email_norm]["name"]
    
    # Then try to match in players.json
    try:
        players_path = Path(__file__).parent.parent / "data" / "players.json"
        if not players_path.exists():
            return None

        players_data = json.loads(players_path.read_text())

        # First: direct email match
        for player in players_data:
            if player.get("email", "").strip().lower() == email_norm:
                return player.get("name")

        # Fallback: prefix matching
        email_prefix = email_norm.split("@")[0].lower()
        for player in players_data:
            full_name = player.get("name", "")
            name_tokens = full_name.lower().split()
            if any(email_prefix.startswith(t) or t.startswith(email_prefix) for t in name_tokens):
                return full_name
            for i in range(1, 5):
                nick = player.get(f"Nick{i}", "").strip().lower()
                if nick and (email_prefix.startswith(nick) or nick.startswith(email_prefix)):
                    return full_name

        return None
    except Exception as e:
        logger.error(f"get_player_name_from_email failed for {email_norm}: {e}")
        return None

# ========================================================================
# USER STORAGE (LOCAL ONLY — GitHub sync handled elsewhere)
# ========================================================================

def _ensure_users_file():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text(json.dumps({}, indent=2))

def load_users_raw() -> Dict:
    _ensure_users_file()
    try:
        return json.loads(USERS_FILE.read_text())
    except Exception:
        return {}

def migrate_users_to_lowercase():
    users = load_users_raw()
    new_users = {}
    changed = False

    for email, data in users.items():
        email_norm = normalize_email(email)
        if email_norm != email:
            changed = True
        new_users[email_norm] = data

    if changed:
        save_users(new_users)
        logger.info("Migrated all user emails to lowercase")

def load_users() -> Dict:
    migrate_users_to_lowercase()
    return load_users_raw()

def save_users(users: Dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))

# ========================================================================
# TOKEN MANAGEMENT
# ========================================================================

def _ensure_token_store():
    TOKEN_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TOKEN_STORE_FILE.exists():
        TOKEN_STORE_FILE.write_text(json.dumps({}, indent=2))

def generate_secure_token() -> str:
    return secrets.token_urlsafe(32)

def store_token(token: str, email: str, token_type: str, expiry_seconds: int):
    _ensure_token_store()
    tokens = json.loads(TOKEN_STORE_FILE.read_text())

    tokens[token] = {
        "email": normalize_email(email),
        "type": token_type,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(seconds=expiry_seconds)).isoformat()
    }

    TOKEN_STORE_FILE.write_text(json.dumps(tokens, indent=2))

def verify_token(token: str, token_type: str) -> Optional[str]:
    _ensure_token_store()
    tokens = json.loads(TOKEN_STORE_FILE.read_text())

    if token not in tokens:
        return None

    token_data = tokens[token]

    if token_data["type"] != token_type:
        return None

    expires_at = datetime.fromisoformat(token_data["expires_at"])
    if datetime.now() > expires_at:
        del tokens[token]
        TOKEN_STORE_FILE.write_text(json.dumps(tokens, indent=2))
        return None

    email = token_data["email"]
    del tokens[token]
    TOKEN_STORE_FILE.write_text(json.dumps(tokens, indent=2))

    return email

# ========================================================================
# PASSWORD HASHING
# ========================================================================

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())

# ========================================================================
# EMAIL SENDING
# ========================================================================

def send_email(recipient_email: str, subject: str, html_body: str) -> bool:
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = SENDER_EMAIL
        message["To"] = recipient_email

        message.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, message.as_string())

        logger.info(f"Email sent to {recipient_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False

def send_verification_email(email: str, token: str, verification_url_base: str) -> bool:
    verification_url = f"{verification_url_base}?token={token}"

    html_body = f"""
    <html>
        <body>
            <h2>Email Verification</h2>
            <p>Please verify your email by clicking the link below:</p>
            <p><a href="{verification_url}">Verify Email</a></p>
        </body>
    </html>
    """

    return send_email(email, "Verify Your Email", html_body)

def send_password_reset_email(email: str, token: str, reset_url_base: str) -> bool:
    reset_url = f"{reset_url_base}?token={token}"

    html_body = f"""
    <html>
        <body>
            <h2>Password Reset</h2>
            <p>Click below to reset your password:</p>
            <p><a href="{reset_url}">Reset Password</a></p>
        </body>
    </html>
    """

    return send_email(email, "Reset Your Password", html_body)

# ========================================================================
# USER MANAGEMENT
# ========================================================================

def user_exists(email: str) -> bool:
    email = normalize_email(email)
    users = load_users()
    return email in users

def create_user(email: str, password: str, role: str = "member") -> Tuple[bool, str]:
    email = normalize_email(email)

    if not validate_email(email):
        return False, "Invalid email format"

    if user_exists(email):
        return False, "User already exists"

    if role not in ["admin", "member"]:
        return False, "Invalid role"

    password_hash = hash_password(password)

    users = load_users()
    users[email] = {
        "password_hash": password_hash,
        "role": role,
        "verified": False,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    save_users(users)

    logger.info(f"User created: {email} (role: {role})")
    return True, "User created successfully"

def verify_user_email(email: str) -> bool:
    email = normalize_email(email)
    users = load_users()

    if email not in users:
        return False

    users[email]["verified"] = True
    users[email]["updated_at"] = datetime.now().isoformat()
    save_users(users)

    logger.info(f"Email verified for user: {email}")
    return True

def is_user_verified(email: str) -> bool:
    email = normalize_email(email)
    users = load_users()
    return users.get(email, {}).get("verified", False)

def get_user_role(email: str) -> Optional[str]:
    email = normalize_email(email)
    users = load_users()
    return users.get(email, {}).get("role")

# ========================================================================
# AUTHENTICATION
# ========================================================================

def authenticate_user(email: str, password: str) -> Tuple[bool, str]:
    email = normalize_email(email)

    if not validate_email(email):
        logger.warning(f"Invalid email format: {email}")
        return False, "Invalid email format"

    users = load_users()

    if email not in users:
        logger.warning(f"Login attempt for non-existent user: {email}")
        return False, "Invalid credentials"

    user = users[email]

    if not user.get("verified", False):
        return False, "Email not verified. Please check your email."

    if not verify_password(password, user["password_hash"]):
        logger.warning(f"Failed login attempt for user: {email}")
        return False, "Invalid credentials"

    logger.info(f"Successful login for user: {email}")
    return True, "Login successful"

def change_password(email: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    email = normalize_email(email)
    users = load_users()

    if email not in users:
        return False, "User not found"

    user = users[email]

    if not verify_password(old_password, user["password_hash"]):
        return False, "Old password is incorrect"

    user["password_hash"] = hash_password(new_password)
    user["updated_at"] = datetime.now().isoformat()
    save_users(users)

    logger.info(f"Password changed for user: {email}")
    return True, "Password changed successfully"

def reset_password(email: str, new_password: str) -> Tuple[bool, str]:
    email = normalize_email(email)
    users = load_users()

    if email not in users:
        return False, "User not found"

    users[email]["password_hash"] = hash_password(new_password)
    users[email]["updated_at"] = datetime.now().isoformat()
    save_users(users)

    logger.info(f"Password reset for user: {email}")
    return True, "Password reset successfully"

# ========================================================================
# AUDIT LOGGING
# ========================================================================

def log_audit_event(event_type: str, email: str, details: str = ""):
    email = normalize_email(email)
    msg = f"[{event_type}] User: {email}"
    if details:
        msg += f" - {details}"
    logger.info(msg)
