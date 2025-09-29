import streamlit as st
import mysql.connector
from mysql.connector import Error
import bcrypt
import datetime
import re
import base64
import logging
import smtplib
from email.mime.text import MIMEText

# Note: boto3, os, and json are NOT imported here.

# --- Logging and Constants ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"

# --- PAGE CONFIGURATION ---
# This must be the first Streamlit command in your script
st.set_page_config(
    page_title="Vclarifi",
    page_icon="images/VTARA.png", # Path to your logo file
    layout="wide"
)
# --- UI Utilities (Self-Contained) ---
def encode_image_to_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        logging.warning(f"Image not found: {path}")
        return None

def set_tm_background(path):
    encoded = encode_image_to_base64(path)
    if encoded:
        st.markdown(f"""<style>[data-testid="stAppViewContainer"] {{
            background-image: url("data:image/jpeg;base64,{encoded}");
            background-size: cover;
        }}</style>""", unsafe_allow_html=True)

# --- Database & Helper Utilities (Receive Secrets) ---
def get_db_connection(secrets):
    try:
        return mysql.connector.connect(
            host=secrets.get("DB_HOST"),
            database=secrets.get("DB_DATABASE"),
            user=secrets.get("DB_USER"),
            password=secrets.get("DB_PASSWORD"),
            port=secrets.get("DB_PORT", 3306)
        )
    except Error as e:
        logging.error(f"DB Connection Error: {e}")
        st.error("Database connection failed.")
        return None

def is_email_invited(email, secrets):
    conn = get_db_connection(secrets)
    if not conn: return None
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT organisation_name FROM admin_team_members WHERE LOWER(team_member_email) = %s"
            cursor.execute(query, (email.strip().lower(),))
            result = cursor.fetchone()
            return result
    finally:
        if conn and conn.is_connected(): conn.close()

def is_email_fully_registered(email, secrets):
    conn = get_db_connection(secrets)
    if not conn: return None
    try:
        with conn.cursor() as cursor:
            query = "SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s"
            cursor.execute(query, (email.strip().lower(),))
            return cursor.fetchone()[0] > 0
    finally:
        if conn and conn.is_connected(): conn.close()

def insert_team_member(tm_data, password, secrets):
    conn = get_db_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            query = """
                INSERT INTO user_registration (
                    first_name, last_name, date_of_birth, age, gender, city, country,
                    organisation_level, organisation_name, designation, sports_team, roles,
                    Email_Id, Password, is_admin
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            """
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            final_args = tm_data + (hashed_password.decode('utf-8'),)
            cursor.execute(query, final_args)
        conn.commit()
        return True
    except Error as e:
        logging.error(f"DB Error inserting team member: {e}")
        st.error("A database error occurred during registration.")
        conn.rollback()
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

def send_confirmation_email(email, name, org_name, secrets):
    SENDER_EMAIL = secrets.get("SENDER_EMAIL")
    SENDER_APP_PASSWORD = secrets.get("SENDER_APP_PASSWORD")
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
        logging.error("Email secrets missing, cannot send confirmation.")
        return

    subject = f"Welcome to VClarifi, {name}!"
    body = f"Hello {name},\n\nYour registration for '{org_name}' is complete. You can now log in."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    try:
        with smtplib.SMTP_SSL(secrets.get("SMTP_SERVER"), int(secrets.get("SMTP_PORT"))) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
    except Exception as e:
        logging.exception(f"Failed to send confirmation email to {email}: {e}")

# --- UI Stage Handlers ---
def handle_email_verification_step(navigate_to, secrets):
    st.subheader("Step 1: Verify Your Invitation Email")
    with st.form("tm_email_verification_form"):
        email = st.text_input("Your Registered Email Address")
        submitted = st.form_submit_button("Verify Email")

    if submitted:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            st.error("Please enter a valid email address.")
        else:
            if is_email_fully_registered(email, secrets):
                st.warning("This email is already fully registered. Please log in.")
            else:
                invitation = is_email_invited(email, secrets)
                if invitation:
                    st.session_state.tm_form_data['email'] = email.lower()
                    st.session_state.tm_form_data['org_name'] = invitation['organisation_name']
                    st.session_state.tm_reg_step = "fill_details"
                    st.success(f"Invitation verified for {invitation['organisation_name']}! Please complete your profile.")
                    st.rerun()
                else:
                    st.error("This email was not found in our list of invited members.")

def handle_details_filling_step(navigate_to, secrets):
    data = st.session_state.tm_form_data
    st.subheader(f"Step 2: Complete Your Profile for '{data['org_name']}'")
    st.markdown(f"Registering with email: **{data['email']}**")

    with st.form("tm_details_form"):
        c1, c2 = st.columns(2)
        data['first_name'] = c1.text_input("First Name*", value=data.get('first_name', ''))
        data['last_name'] = c2.text_input("Last Name*", value=data.get('last_name', ''))
        password = c1.text_input("Create Password* (min 8 characters)", type="password")
        confirm_password = c2.text_input("Confirm Password*", type="password")
        data['dob'] = c1.date_input("Date of Birth*", value=data.get('dob', datetime.date.today() - datetime.timedelta(days=365*18)))
        data['age'] = c2.number_input("Age*", min_value=5, value=data.get('age', 18))
        
        submitted = st.form_submit_button("Register My Profile")

    if submitted:
        errors = []
        if not data['first_name'] or not data['last_name']: errors.append("First and Last Name are required.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_password: errors.append("Passwords do not match.")
        
        if errors:
            for error in errors: st.error(f"⚠️ {error}")
        else:
            # Prepare data for DB
            tm_data_for_db = (
                data['first_name'], data['last_name'], data['dob'].strftime('%Y-%m-%d'), data['age'],
                "Not Specified", None, None, "Team Member", data['org_name'],
                None, None, "Athlete/Player", data['email']
            )
            if insert_team_member(tm_data_for_db, password, secrets):
                st.success(f"Welcome, {data['first_name']}! Your registration is complete.")
                send_confirmation_email(data['email'], data['first_name'], data['org_name'], secrets)
                # Clean up and navigate
                del st.session_state.tm_reg_step
                del st.session_state.tm_form_data
                if 'registration_choice' in st.session_state: del st.session_state.registration_choice
                navigate_to('login')
                st.rerun()

    if st.button("Cancel and Go Back"):
        # Reset state and go back to main registration choices
        del st.session_state.tm_reg_step
        del st.session_state.tm_form_data
        st.session_state.registration_choice = None
        st.rerun()

# --- Main Entry Point for this File ---
def render_team_member_registration_view(navigate_to, secrets):
    """
    Main entry point called by the user_registration.py router.
    Args:
        navigate_to (function): Callback function to switch pages.
        secrets (dict): Dictionary containing the application secrets.
    """
    set_tm_background(BG_IMAGE_PATH)
    st.markdown("<h1>Team Member / Athlete Registration</h1>", unsafe_allow_html=True)

    # Initialize state for this specific registration flow
    if "tm_reg_step" not in st.session_state:
        st.session_state.tm_reg_step = "verify_email"
    if "tm_form_data" not in st.session_state:
        st.session_state.tm_form_data = {}

    # State machine for registration steps
    if st.session_state.tm_reg_step == "verify_email":
        handle_email_verification_step(navigate_to, secrets)
    elif st.session_state.tm_reg_step == "fill_details":
        handle_details_filling_step(navigate_to, secrets)
