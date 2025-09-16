import base64
import logging
import random
import re
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import bcrypt
import mysql.connector
from mysql.connector import Error
import streamlit as st

# ---------- LOGGING AND CONSTANTS ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
RESET_CODE_EXPIRY_MINUTES = 15
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"

# ---------- STREAMLIT PAGE CONFIGURATION ----------
try:
    st.set_page_config(page_title="Forgot Password - VClarifi", layout="centered")
except st.errors.StreamlitAPIException:
    pass # Ignore if main.py already set it

# ---------- MAIN UI CONTROLLER ----------
def render_forgot_password_page(navigate_to, secrets):
    """
    Renders the forgot password page.
    Args:
        navigate_to (function): Callback to navigate to other pages.
        secrets (dict): Dictionary containing application secrets.
    """
    set_background(BG_IMAGE_PATH)
    display_logo(LOGO_IMAGE_PATH)
    st.title("🔑 Reset Your Password")

    if 'forgot_password_stage' not in st.session_state:
        st.session_state.forgot_password_stage = "enter_email"

    stage = st.session_state.forgot_password_stage
    if stage == "enter_email":
        handle_email_stage(navigate_to, secrets)
    elif stage == "enter_code":
        handle_code_stage(navigate_to, secrets)
    elif stage == "reset_password":
        handle_reset_stage(navigate_to, secrets)
    elif stage == "reset_success":
        handle_success_stage(navigate_to)

# ---------- UI STAGE HANDLERS ----------
def handle_email_stage(navigate_to, secrets):
    with st.form("email_verification_form"):
        email = st.text_input("Enter your registered Email Address:")
        submitted = st.form_submit_button("Send Verification Code")

    if submitted:
        if not email or not is_valid_email_format(email):
            st.warning("Please enter a valid email address.")
        else:
            exists, db_error = check_email_exists(email, secrets)
            if exists:
                code = generate_verification_code()
                if store_verification_code(email, code, secrets) and send_verification_code_email(email, code, secrets):
                    st.session_state.reset_email = email
                    st.session_state.forgot_password_stage = "enter_code"
                    st.success(f"A code has been sent to {email}.")
                    st.rerun()
                else:
                    st.error("Could not send verification email.")
            elif not db_error:
                st.error("This email is not registered.")

    if st.button("Back to Login", type="secondary"): navigate_to("login")

def handle_code_stage(navigate_to, secrets):
    email = st.session_state.get('reset_email', '')
    st.info(f"A code was sent to **{email}**. It expires in {RESET_CODE_EXPIRY_MINUTES} minutes.")
    with st.form("code_verification_form"):
        code = st.text_input("Enter 6-Digit Code:", max_chars=6)
        submitted = st.form_submit_button("Verify Code")

    if submitted:
        if verify_code_from_db(email, code, secrets):
            st.session_state.verified_reset_code = code
            st.session_state.forgot_password_stage = "reset_password"
            st.success("Code verified.")
            st.rerun()
        else:
            st.error("Invalid, expired, or used code.")
            
    # ... (rest of the stage handlers follow the same pattern) ...

# (The rest of the file, including all database and email utilities,
#  must be updated to accept 'secrets' as an argument, just like the example below)

# ---------- DATABASE UTILITIES (EXAMPLE) ----------
def get_connection(secrets):
    """Establishes a database connection using passed-in secrets."""
    try:
        return mysql.connector.connect(
            host=secrets.get("DB_HOST"),
            database=secrets.get("DB_DATABASE"),
            user=secrets.get("DB_USER"),
            password=secrets.get("DB_PASSWORD")
        )
    except Error as err:
        logging.error(f"DB connection error: {err}")
        st.error("Database connection error.")
        return None

def check_email_exists(email, secrets):
    """Checks if an email exists in the database."""
    conn = get_connection(secrets)
    if not conn: return False, True
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM user_registration WHERE Email_Id = %s LIMIT 1", (email,))
            return cursor.fetchone() is not None, False
    except Error as err:
        logging.error(f"DB error checking email: {err}")
        st.error("Database error while checking email.")
        return False, True
    finally:
        if conn and conn.is_connected(): conn.close()

# (Continue this pattern for all other utility functions:
# store_verification_code, verify_code_from_db, update_password_in_db,
# send_verification_code_email, etc. Each one needs to accept 'secrets'
# and use it to get DB/email credentials.)

# ---------- HELPER UTILITIES ----------
def is_valid_email_format(email):
    """Validates email format using regex."""
    if not email: return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_verification_code(length=6):
    """Generates a random numerical code."""
    return ''.join(random.choice(string.digits) for _ in range(length))
