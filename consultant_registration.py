import streamlit as st
import datetime
import base64
import mysql.connector
from mysql.connector import Error
import bcrypt
import re
import logging
import smtplib
from email.mime.text import MIMEText

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
BG_IMAGE_PATH = "images/background.jpg"
PREDEFINED_COUNTRIES = ["Select Country", "India", "Australia"]
AREAS_OF_EXPERTISE = [
    "Sports Psychology", "Physiotherapy", "Strength & Conditioning",
    "Sports Nutrition", "Data Analytics", "Sports Management", "Other"
]

# --- Shared UI Utilities ---
def set_consultant_background(path):
    try:
        with open(path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpeg;base64,{encoded}");
                background-size: cover;
            }}
            </style>""", unsafe_allow_html=True)
    except FileNotFoundError:
        logging.warning(f"Background image not found: {path}")

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
        logging.error(f"Database Connection Error: {e}")
        st.error("Database connection failed.")
        return None

def email_exists_in_users(email, secrets):
    conn = get_db_connection(secrets)
    if not conn: return True # Fail safe
    try:
        with conn.cursor() as cursor:
            query = "SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s"
            cursor.execute(query, (email.strip().lower(),))
            return cursor.fetchone()[0] > 0
    except Error as e:
        logging.error(f"DB Error checking email existence: {e}")
        return True # Fail safe
    finally:
        if conn and conn.is_connected(): conn.close()

def insert_consultant_data(user_data, consultant_data, password, secrets):
    conn = get_db_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            # Step 1: Insert into user_registration
            user_query = """
                INSERT INTO user_registration (
                    first_name, last_name, date_of_birth, age, gender, city, country, Email_Id,
                    Password, is_admin, organisation_level
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, 'Consultant')
            """
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            user_args = user_data + (hashed_password.decode('utf-8'),)
            cursor.execute(user_query, user_args)

            # Step 2: Insert into consultant_details
            consultant_query = """
                INSERT INTO consultant_details (
                    email_id, area_of_expertise, years_of_experience, certifications, bio,
                    availability, preferred_sports_focus, linkedin_url, website_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            # Prepend email to the consultant data tuple
            consultant_args = (user_data[7],) + consultant_data
            cursor.execute(consultant_query, consultant_args)
        
        conn.commit()
        return True
    except Error as e:
        logging.error(f"DB Error during consultant insertion: {e}")
        conn.rollback()
        st.error("A database error occurred during registration.")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Main Entry Point for This File ---
def render_consultant_registration_view(navigate_to, secrets):
    """
    Main entry point called by the user_registration.py router.
    Args:
        navigate_to (function): Callback function to switch pages.
        secrets (dict): Dictionary containing the application secrets.
    """
    set_consultant_background(BG_IMAGE_PATH)
    st.markdown("<h1>Consultant Registration</h1>", unsafe_allow_html=True)

    # Simplified session state management
    if 'consultant_form_data' not in st.session_state:
        st.session_state.consultant_form_data = {
            "first_name": "", "last_name": "", "email": "",
            "dob": datetime.date.today() - datetime.timedelta(days=365*25),
            "age": 25, "gender": "Select", "country": "Select Country",
            "expertise": [], "experience": 0, "certifications": "", "bio": "",
            "availability": "Select Availability", "sports_focus": "", "linkedin": "", "website": ""
        }
    
    data = st.session_state.consultant_form_data

    with st.form("consultant_reg_form"):
        st.markdown("### Personal Details")
        c1, c2 = st.columns(2)
        data['first_name'] = c1.text_input("First Name*", value=data['first_name'])
        data['last_name'] = c2.text_input("Last Name*", value=data['last_name'])
        data['email'] = st.text_input("Email ID*", value=data['email'])
        password = st.text_input("Create Password* (min 8 characters)", type="password")
        confirm_password = st.text_input("Confirm Password*", type="password")

        st.markdown("### Professional Details")
        data['expertise'] = st.multiselect("Area(s) of Expertise*", AREAS_OF_EXPERTISE, default=data['expertise'])
        data['experience'] = st.number_input("Years of Experience*", min_value=0, step=1, value=data['experience'])
        data['linkedin'] = st.text_input("LinkedIn Profile URL (Optional)", value=data['linkedin'])

        submitted = st.form_submit_button("Confirm Consultant Registration")

    if submitted:
        # --- Start Validation ---
        errors = []
        email_lower = data['email'].lower()
        if not data['first_name'] or not data['last_name']: errors.append("First and Last Name are required.")
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_lower):
            errors.append("A valid Email is required.")
        elif email_exists_in_users(email_lower, secrets):
            errors.append(f"The email '{data['email']}' is already registered.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_password: errors.append("Passwords do not match.")
        if not data['expertise']: errors.append("At least one Area of Expertise is required.")
        # --- End Validation ---

        if errors:
            for error in errors:
                st.error(f"⚠️ {error}")
        else:
            # Prepare data for DB insertion
            user_data_for_db = (
                data['first_name'], data['last_name'], data['dob'].strftime('%Y-%m-%d'),
                data['age'], "Not Specified", None, None, email_lower
            )
            consultant_data_for_db = (
                ", ".join(data['expertise']), data['experience'], None, None,
                "Not Specified", None, data['linkedin'] or None, None
            )

            if insert_consultant_data(user_data_for_db, consultant_data_for_db, password, secrets):
                st.success("✅ Consultant registration successful! Please log in.")
                st.balloons()
                # Clear form data from session state
                del st.session_state.consultant_form_data
                if 'registration_choice' in st.session_state: del st.session_state.registration_choice
                navigate_to('login')
                st.rerun()

    if st.button("Cancel and Go Back"):
        # Clear form data from session state
        if 'consultant_form_data' in st.session_state: del st.session_state.consultant_form_data
        if 'registration_choice' in st.session_state: st.session_state.registration_choice = None
        st.rerun()
