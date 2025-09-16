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

    if st.button("Resend Code", type="secondary"):
        new_code = generate_verification_code()
        if store_verification_code(email, new_code, secrets) and send_verification_code_email(email, new_code, secrets):
            st.success("A new code has been sent.")
            st.rerun()

def handle_reset_stage(navigate_to, secrets):
    email = st.session_state.get('reset_email', '')
    st.info(f"Create a new password for: **{email}**")
    with st.form("new_password_form"):
        new_password = st.text_input("New Password:", type="password")
        confirm_password = st.text_input("Confirm New Password:", type="password")
        submitted = st.form_submit_button("Set New Password")

    if submitted:
        if not new_password or len(new_password) < 8:
            st.warning("Password must be at least 8 characters.")
        elif new_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            if update_password_in_db(email, new_password, secrets):
                mark_code_as_used(email, st.session_state.verified_reset_code, secrets)
                send_password_change_email(email, secrets)
                st.session_state.forgot_password_stage = "reset_success"
                st.balloons()
                st.rerun()

def handle_success_stage(navigate_to):
    st.success("Your password has been successfully reset!")
    if st.button("Proceed to Login"):
        # Clean up session state
        for key in ['forgot_password_stage', 'reset_email', 'verified_reset_code']:
            if key in st.session_state:
                del st.session_state[key]
        navigate_to("login")

# ---------- UI UTILITY FUNCTIONS ----------
def encode_image_to_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        logging.warning(f"Image file not found at {path}.")
        return None

def set_background(path):
    encoded_image = encode_image_to_base64(path)
    if encoded_image:
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded_image}");
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)

def display_logo(path):
    encoded_logo = encode_image_to_base64(path)
    if encoded_logo:
        st.markdown(f"""
        <div style='position:fixed; top:25px; right:35px; z-index:999'>
            <img src="data:image/png;base64,{encoded_logo}" alt="Logo" style="width:60px;">
        </div>
        """, unsafe_allow_html=True)

# ---------- DATABASE UTILITIES ----------
def get_connection(secrets):
    try:
        return mysql.connector.connect(
            host=secrets.get("DB_HOST"),
            database=secrets.get("DB_DATABASE"),
            user=secrets.get("DB_USER"),
            password=secrets.get("DB_PASSWORD"),
            port=secrets.get("DB_PORT", 3306)
        )
    except Error as err:
        logging.error(f"DB connection error: {err}")
        st.error("Database connection error.")
        return None

def check_email_exists(email, secrets):
    conn = get_connection(secrets)
    if not conn: return False, True
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM user_registration WHERE Email_Id = %s LIMIT 1", (email,))
            return cursor.fetchone() is not None, False
    except Error as err:
        logging.error(f"DB error checking email: {err}")
        return False, True
    finally:
        if conn and conn.is_connected(): conn.close()

def store_verification_code(email, code, secrets):
    conn = get_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            now = datetime.now()
            expires_at = now + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)
            query = """
            INSERT INTO password_reset_codes (email, reset_code, created_at, expires_at, used)
            VALUES (%s, %s, %s, %s, FALSE)
            ON DUPLICATE KEY UPDATE
            reset_code = VALUES(reset_code), created_at = VALUES(created_at),
            expires_at = VALUES(expires_at), used = VALUES(used);
            """
            cursor.execute(query, (email, code, now, expires_at))
        conn.commit()
        return True
    except Error as err:
        logging.error(f"DB error storing code: {err}")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

def verify_code_from_db(email, code, secrets):
    conn = get_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT expires_at, used FROM password_reset_codes WHERE email = %s AND reset_code = %s"
            cursor.execute(query, (email, code))
            record = cursor.fetchone()
        if record and not record['used'] and record['expires_at'] > datetime.now():
            return True
        return False
    except Error as err:
        logging.error(f"DB error verifying code: {err}")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

def mark_code_as_used(email, code, secrets):
    conn = get_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            query = "UPDATE password_reset_codes SET used = TRUE WHERE email = %s AND reset_code = %s"
            cursor.execute(query, (email, code))
        conn.commit()
        return True
    except Error as err:
        logging.error(f"DB error marking code as used: {err}")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

def update_password_in_db(email, new_password, secrets):
    conn = get_connection(secrets)
    if not conn: return False
    try:
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        with conn.cursor() as cursor:
            cursor.execute("UPDATE user_registration SET Password = %s WHERE Email_Id = %s", (hashed, email))
        conn.commit()
        return True
    except Error as err:
        logging.error(f"DB error updating password: {err}")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

# ---------- EMAIL UTILITIES ----------
def send_verification_code_email(to_email, code, secrets):
    SENDER_EMAIL = secrets.get("SENDER_EMAIL")
    SENDER_APP_PASSWORD = secrets.get("SENDER_APP_PASSWORD")
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD: return False
    
    msg = MIMEText(f"Your VClarifi password reset code is: {code}")
    msg['Subject'] = "VClarifi Password Reset Code"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL(secrets.get("SMTP_SERVER"), int(secrets.get("SMTP_PORT"))) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        logging.exception(f"Email error: {e}")
        return False

def send_password_change_email(to_email, secrets):
    SENDER_EMAIL = secrets.get("SENDER_EMAIL")
    SENDER_APP_PASSWORD = secrets.get("SENDER_APP_PASSWORD")
    if not SENDER_EMAIL: return False
    
    msg = MIMEText("Your password for VClarifi has been successfully changed.")
    msg['Subject'] = "Password Reset Confirmation"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL(secrets.get("SMTP_SERVER"), int(secrets.get("SMTP_PORT"))) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        logging.exception(f"Email confirmation error: {e}")
        return False

# ---------- HELPER UTILITIES ----------
def is_valid_email_format(email):
    if not email: return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_verification_code(length=6):
    return ''.join(random.choice(string.digits) for _ in range(length))
