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

# ---------- LOGGING CONFIGURATION ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

# ---------- CONSTANTS AND STATIC CONFIGURATION ----------
RESET_CODE_EXPIRY_MINUTES = 15
# TODO: Update with the correct absolute or relative paths for your project.
BG_IMAGE_PATH = "C:/Users/DELL/Desktop/background.jpg"
LOGO_IMAGE_PATH = "C:/Users/DELL/Desktop/VTARA.png"

# ---------- GLOBAL CONFIGURATION (USER-SPECIFIED METHOD) ----------
# This block attempts to load all secrets into global variables. If it fails,
# it sets them to None and logs a critical error, preventing the app from crashing.
try:
    DB_HOST = st.secrets.database.DB_HOST
    DB_DATABASE = st.secrets.database.DB_DATABASE
    DB_USER = st.secrets.database.DB_USER
    DB_PASSWORD = st.secrets.database.DB_PASSWORD

    SENDER_EMAIL = st.secrets.email.SENDER_EMAIL
    SENDER_APP_PASSWORD = st.secrets.email.SENDER_APP_PASSWORD
    SMTP_SERVER = st.secrets.email.SMTP_SERVER
    SMTP_PORT = st.secrets.email.SMTP_PORT

    CONFIG_LOADED_SUCCESSFULLY = True
    logging.info("Configuration secrets loaded successfully.")

except (AttributeError, KeyError) as e:
    logging.critical(f"FATAL: Could not read secrets from secrets.toml. Check file location and keys. Error: {e}")
    # Display the error on the page if Streamlit has started enough to do so.
    st.error("Application is critically misconfigured. Please contact an administrator.")
    # Set all config variables to None so the app can still load without crashing.
    DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
    SENDER_EMAIL = SENDER_APP_PASSWORD = SMTP_SERVER = SMTP_PORT = None
    CONFIG_LOADED_SUCCESSFULLY = False


# ---------- STREAMLIT PAGE CONFIGURATION ----------
try:
    st.set_page_config(page_title="Forgot Password - VClarifi", layout="centered")
except st.errors.StreamlitAPIException as e:
    if "st.set_page_config() has already been called" not in str(e):
        raise

# ---------- MAIN UI CONTROLLER ----------
def render_forgot_password_page(navigate_to):
    """
    Renders the main multi-stage forgot password page and handles its state.
    Args:
        navigate_to (function): A callback function to navigate to other pages.
    """
    set_background(BG_IMAGE_PATH)
    display_logo(LOGO_IMAGE_PATH)

    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.title("🔑 Reset Your Password")
    st.markdown("---")

    if not CONFIG_LOADED_SUCCESSFULLY:
        st.warning("Cannot proceed because the application configuration failed to load.")
        return

    # Initialize session state for the forgot password flow
    if 'forgot_password_stage' not in st.session_state:
        st.session_state.forgot_password_stage = "enter_email"

    # UI State Machine
    if st.session_state.forgot_password_stage == "enter_email":
        handle_email_stage(navigate_to)
    elif st.session_state.forgot_password_stage == "enter_code":
        handle_code_stage(navigate_to)
    elif st.session_state.forgot_password_stage == "reset_password":
        handle_reset_stage(navigate_to)
    elif st.session_state.forgot_password_stage == "reset_success":
        handle_success_stage(navigate_to)

# ---------- UI STAGE HANDLERS ----------
def handle_email_stage(navigate_to):
    """UI and logic for the 'enter_email' stage."""
    with st.form("email_verification_form"):
        email_input = st.text_input(
            "Enter your registered Email Address:",
            key="fp_email_input",
            value=st.session_state.get("fp_email_form_val", "")
        )
        submitted = st.form_submit_button("Send Verification Code")

    if submitted:
        st.session_state.fp_email_form_val = email_input
        if not email_input:
            st.warning("Email address is required.")
        elif not is_valid_email_format(email_input):
            st.warning("Please enter a valid email address format.")
        else:
            email_exists, is_db_error = check_email_exists(email_input)
            if email_exists:
                code = generate_verification_code()
                if store_verification_code(email_input, code) and send_verification_code_email(email_input, code):
                    st.session_state.reset_email = email_input
                    st.session_state.forgot_password_stage = "enter_code"
                    if "fp_email_form_val" in st.session_state:
                        del st.session_state.fp_email_form_val
                    st.success(f"A 6-digit verification code has been sent to {email_input}. Please check your inbox (and spam folder).")
                    st.rerun()
                else:
                    st.error("Could not send verification email due to a server issue. Please try again or contact support.")
            elif not is_db_error:
                st.error("This email address is not registered with VClarifi.")
            # If is_db_error is True, an error message was already displayed by a lower-level function.

    st.markdown("---")
    if st.button("Back to Login", key="fp_back_to_login_email_stage", type="secondary"):
        navigate_to("login")

def handle_code_stage(navigate_to):
    """UI and logic for the 'enter_code' stage."""
    st.info(f"A 6-digit verification code was sent to **{st.session_state.get('reset_email', '')}**. It will expire in {RESET_CODE_EXPIRY_MINUTES} minutes.")
    with st.form("code_verification_form"):
        code_input = st.text_input("Enter 6-Digit Verification Code:", key="fp_code_input", max_chars=6)
        submitted = st.form_submit_button("Verify Code")

    if submitted:
        if not code_input:
            st.warning("Verification code is required.")
        elif not code_input.isdigit() or len(code_input) != 6:
            st.warning("Please enter a valid 6-digit numerical code.")
        else:
            if verify_code_from_db(st.session_state.reset_email, code_input):
                st.session_state.verified_reset_code = code_input
                st.session_state.forgot_password_stage = "reset_password"
                st.success("Code verified successfully. You can now set a new password.")
                st.rerun()
            else:
                st.error("Invalid, expired, or already used verification code. Please check the code or request a new one.")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Resend Code", key="fp_resend_code", type="secondary"):
            code = generate_verification_code()
            if store_verification_code(st.session_state.reset_email, code) and send_verification_code_email(st.session_state.reset_email, code):
                st.success(f"A new 6-digit verification code has been sent.")
                st.rerun()
            else:
                st.error("Failed to resend verification code. Please try again later.")
    with col2:
        if st.button("Change Email", key="fp_change_email", type="secondary"):
            st.session_state.forgot_password_stage = "enter_email"
            st.rerun()

def handle_reset_stage(navigate_to):
    """UI and logic for the 'reset_password' stage."""
    st.info(f"Create a new password for your account: **{st.session_state.get('reset_email', '')}**")
    with st.form("new_password_form"):
        new_password = st.text_input("New Password:", type="password", key="fp_new_password")
        confirm_password = st.text_input("Confirm New Password:", type="password", key="fp_confirm_password")
        submitted = st.form_submit_button("Set New Password")

    if submitted:
        if not new_password or not confirm_password:
            st.warning("Both password fields are required.")
        elif len(new_password) < 8:
            st.error("Password must be at least 8 characters long.")
        elif new_password != confirm_password:
            st.warning("The new passwords do not match.")
        else:
            if update_password_in_db(st.session_state.reset_email, new_password):
                mark_code_as_used(st.session_state.reset_email, st.session_state.verified_reset_code)
                send_password_change_email(st.session_state.reset_email)
                st.session_state.forgot_password_stage = "reset_success"
                st.balloons()
                st.rerun()
            else:
                st.error("Failed to update your password due to a server issue. Please try again.")

    st.markdown("---")
    if st.button("Back to Code Entry", key="fp_back_to_code_stage", type="secondary"):
        st.session_state.forgot_password_stage = "enter_code"
        st.rerun()

def handle_success_stage(navigate_to):
    """UI and logic for the final 'reset_success' stage."""
    st.success("Your password has been successfully reset!")
    st.info("You can now proceed to the login page with your new password.")
    if st.button("Proceed to Login", key="fp_proceed_to_login_success"):
        keys_to_delete = ['forgot_password_stage', 'reset_email', 'verified_reset_code', 'fp_email_form_val']
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
        navigate_to("login")
        st.rerun()

# ---------- IMAGE AND UI UTILITIES ----------
def encode_image_to_base64(path):
    """Encodes an image file to a base64 string for embedding in HTML/CSS."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        logging.warning(f"Image file not found at {path}.")
        return None
    except Exception as e:
        logging.error(f"Error encoding image {path}: {e}")
        return None

def set_background(path):
    """
    Sets the Streamlit page background using a base64 encoded image.
    This version applies the background to the main app container for full coverage.
    """
    encoded_image = encode_image_to_base64(path)
    if encoded_image:
        # This CSS targets the main Streamlit app container.
        # `background-size: cover` ensures the image fills the screen.
        # `background-attachment: fixed` prevents the background from scrolling.
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded_image}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        [data-testid="stHeader"], [data-testid="stToolbar"] {{
            background: rgba(0,0,0,0);
        }}
        </style>
        """, unsafe_allow_html=True)

def display_logo(path):
    """Displays the application logo at the top right of the page."""
    encoded_logo = encode_image_to_base64(path)
    if encoded_logo:
        st.markdown(f"""
        <div style='position:fixed; top:25px; right:35px; display:flex; align-items:center; gap:10px; z-index:999'>
            <img src="data:image/png;base64,{encoded_logo}" alt="VClarifi Logo" style="width:60px; height:auto;">
            <div style='font-weight:bold; font-size:24px; color:white; text-shadow: 1px 1px 3px #000;'>VCLARIFI</div>
        </div>
        """, unsafe_allow_html=True)


# ---------- DATABASE UTILITIES ----------
def get_connection():
    """Establishes and returns a database connection using global config variables."""
    if not DB_HOST: # A quick check for one of the essential DB variables.
        logging.error("Database connection attempt failed because secrets were not loaded.")
        st.error("Database is not configured. Cannot proceed.")
        return None
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            database=DB_DATABASE,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Error as err:
        logging.error(f"Database connection error: {err}")
        st.error("A database connection error occurred. Please check credentials or contact support.")
        return None

def check_email_exists(email):
    """
    Checks if an email exists in the user registration table.
    Returns: tuple[bool, bool]: A tuple containing (email_exists, is_db_error).
    """
    conn = get_connection()
    if not conn:
        return False, True
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM user_registration WHERE Email_Id = %s LIMIT 1", (email,))
            exists = cursor.fetchone() is not None
        return exists, False
    except Error as err:
        logging.error(f"DB error checking email {email}: {err}")
        st.error("A database error occurred while verifying your email.")
        return False, True
    finally:
        if conn and conn.is_connected():
            conn.close()

def store_verification_code(email, code):
    """Saves or updates a password reset code in the database."""
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            now = datetime.now()
            expires_at = now + timedelta(minutes=RESET_CODE_EXPIRY_MINUTES)
            query = """INSERT INTO password_reset_codes (email, reset_code, created_at, expires_at, used) VALUES (%s, %s, %s, %s, FALSE) ON DUPLICATE KEY UPDATE reset_code = VALUES(reset_code), created_at = VALUES(created_at), expires_at = VALUES(expires_at), used = VALUES(used);"""
            cursor.execute(query, (email, code, now, expires_at))
        conn.commit()
        logging.info(f"Stored/Updated verification code for {email}.")
        return True
    except Error as err:
        logging.error(f"DB error storing verification code for {email}: {err}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def verify_code_from_db(email, code):
    """Verifies if the provided code is valid, unused, and not expired."""
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT expires_at, used FROM password_reset_codes WHERE email = %s AND reset_code = %s"
            cursor.execute(query, (email, code))
            record = cursor.fetchone()
        if record and not record['used'] and record['expires_at'] > datetime.now():
            return True
        elif record:
            logging.warning(f"Failed verification for {email}. Used: {record['used']}, Expired: {record['expires_at'] <= datetime.now()}")
        return False
    except Error as err:
        logging.error(f"DB error verifying code for {email}: {err}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def mark_code_as_used(email, code):
    """Marks a verification code as used in the database to prevent reuse."""
    conn = get_connection()
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            query = "UPDATE password_reset_codes SET used = TRUE WHERE email = %s AND reset_code = %s"
            cursor.execute(query, (email, code))
        conn.commit()
        logging.info(f"Successfully marked code as used for {email}.")
        return True
    except Error as err:
        logging.error(f"DB error marking code as used for {email}: {err}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

def update_password_in_db(email, new_password):
    """Hashes and updates the user's password in the database."""
    conn = get_connection()
    if not conn: return False
    try:
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        with conn.cursor() as cursor:
            cursor.execute("UPDATE user_registration SET Password = %s WHERE Email_Id = %s", (hashed, email))
        conn.commit()
        logging.info(f"Password successfully updated in DB for {email}.")
        return True
    except Error as err:
        logging.error(f"Password update database error for {email}: {err}")
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()

# ---------- EMAIL UTILITIES ----------
def is_valid_email_format(email):
    """Validates email format using a regular expression."""
    if not email: return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_verification_code_email(to_email, code):
    """Constructs and sends the verification code to the user's email."""
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
        logging.error("Email sending failed because email secrets were not loaded.")
        return False
    msg_body = (f"Hello,\n\n"
                f"You requested a password reset for your VClarifi account.\n"
                f"Your 6-digit verification code is: {code}\n\n"
                f"This code will expire in {RESET_CODE_EXPIRY_MINUTES} minutes.\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"Sincerely,\nThe VClarifi Team")
    msg = MIMEText(msg_body)
    msg['Subject'] = "VClarifi Password Reset Verification Code"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        logging.info(f"Verification code successfully sent to {to_email}.")
        return True
    except Exception as e:
        logging.exception(f"Email Service: Unexpected error sending verification code: {e}")
        return False

def send_password_change_email(to_email):
    """Sends a final confirmation email after a successful password change."""
    if not SENDER_EMAIL: return False
    msg_body = (f"Hello,\n\n"
                f"Your password for the VClarifi account associated with {to_email} has been successfully changed.\n\n"
                f"If you did not make this change, please contact our support team immediately.\n\n"
                f"Sincerely,\nThe VClarifi Team")
    msg = MIMEText(msg_body)
    msg['Subject'] = "VClarifi Password Reset Confirmation"
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        logging.info(f"Password change notification sent to {to_email}.")
        return True
    except Exception as e:
        logging.exception(f"Email Service: Failed to send final confirmation: {e}")
        return False

# ---------- HELPER UTILITIES ----------
def generate_verification_code(length=6):
    """Generates a random numerical code of a given length."""
    return ''.join(random.choice(string.digits) for _ in range(length))

# ---------- STANDALONE TEST BLOCK ----------
if __name__ == "__main__":
    st.info("Running `forgot.py` in standalone test mode.")

    def dummy_navigator(page_name):
        """Simulates navigation for testing purposes."""
        st.toast(f"Navigating to: {page_name}")
        logging.info(f"Dummy navigation to '{page_name}' triggered.")
        if page_name == "login":
            st.session_state.current_page_mock = "login_mock_display"
            st.rerun()

    if st.session_state.get("current_page_mock") == "login_mock_display":
        st.empty()
        st.title("Mock Login Page")
        st.write("You would log in here. The forgot password flow is complete.")
        if st.button("Test Forgot Password Again"):
            keys_to_delete = ['forgot_password_stage', 'reset_email', 'verified_reset_code',
                              'fp_email_form_val', 'current_page_mock']
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    else:
        render_forgot_password_page(dummy_navigator)