"""
Admin Page for GOAM Admin
Allows:
- Viewing all users
- Creating new users
- Editing roles
- Verifying accounts
- Resetting passwords
- Deleting users
"""

import streamlit as st
from datetime import datetime

from auth.auth import (
    load_users,
    save_users,
    create_user,
    reset_password
)

# NEW: GitHub sync
from utils.github_storage import save_user_record


# ========================================================================
# ADMIN PAGE
# ========================================================================

def show_admin_page(admin_email: str):
    st.title("🛠️ User Management (Admin Only)")

    users = load_users()

    # ====================================================================
    # CREATE NEW USER
    # ====================================================================

    st.subheader("➕ Create New User")

    with st.expander("Add User"):
        new_email = st.text_input("Email")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["member", "admin"])

        if st.button("Create User", use_container_width=True):
            email_norm = new_email.strip().lower()

            if not new_email or not new_password:
                st.error("Email and password are required")
            elif email_norm in users:
                st.error("User already exists")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters")
            else:
                ok, msg = create_user(email_norm, new_password, new_role)
                if ok:
                    # 🔥 Sync to GitHub
                    save_user_record(email_norm, load_users()[email_norm])

                    st.success("User created successfully!")
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("---")

    # ====================================================================
    # USER TABLE
    # ====================================================================

    st.subheader("📋 All Users")

    if not users:
        st.info("No users found.")
        return

    for email, user in users.items():
        with st.container():
            st.markdown(f"### {email}")

            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            # ------------------ USER INFO ------------------
            with col1:
                st.write(f"**Role:** {user.get('role', 'member').capitalize()}")
                st.write(f"**Verified:** {'Yes' if user.get('verified') else 'No'}")
                st.write(f"**Created:** {user.get('created_at', 'N/A')}")
                st.write(f"**Updated:** {user.get('updated_at', 'N/A')}")

            # ------------------ ROLE UPDATE ------------------
            with col2:
                new_role = st.selectbox(
                    f"Role for {email}",
                    ["member", "admin"],
                    index=0 if user.get("role") == "member" else 1,
                    key=f"role_{email}"
                )
                if st.button(f"Update Role ({email})"):
                    user["role"] = new_role
                    user["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    users[email] = user
                    save_users(users)

                    # 🔥 Sync to GitHub
                    save_user_record(email, user)

                    st.success("Role updated")
                    st.rerun()

            # ------------------ VERIFY + RESET PASSWORD ------------------
            with col3:
                if not user.get("verified"):
                    if st.button(f"Verify {email}"):
                        user["verified"] = True
                        user["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        users[email] = user
                        save_users(users)

                        # 🔥 Sync to GitHub
                        save_user_record(email, user)

                        st.success("User verified")
                        st.rerun()

                new_pw = st.text_input(
                    f"New Password ({email})",
                    type="password",
                    key=f"pw_{email}"
                )
                if st.button(f"Reset Password ({email})"):
                    if len(new_pw) < 8:
                        st.error("Password must be at least 8 characters")
                    else:
                        ok, msg = reset_password(email, new_pw)
                        if ok:
                            user["updated_at"] = datetime.now().isoformat()
                            users[email] = user
                            save_users(users)

                            # 🔥 Sync to GitHub
                            save_user_record(email, user)

                            st.success("Password updated")
                            st.rerun()
                        else:
                            st.error(msg)

            # ------------------ DELETE USER ------------------
            with col4:
                if email != admin_email:
                    if st.button(f"Delete {email}"):
                        del users[email]
                        save_users(users)

                        # 🔥 Sync delete to GitHub
                        save_user_record(email, None)

                        st.warning(f"User {email} deleted")
                        st.rerun()

    st.markdown("---")

