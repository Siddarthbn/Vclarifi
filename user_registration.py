import streamlit as st
import datetime
import os
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
LOGO_IMAGE_PATH = "images/vtara.png"
PREDEFINED_COUNTRIES = ["Select Country", "India", "Australia"]
COUNTRY_CITIES_MAP = {
    "India": ["Select City", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"],
    "Australia": ["Select City", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
}

# --- Shared UI Utilities ---
def set_registration_background(path_to_image):
    try:
        with open(path_to_image, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpeg;base64,{encoded}");
                background-size: cover;
            }}
            </style>""", unsafe_allow_html=True)
    except FileNotFoundError:
        logging.warning(f"Background image not found: {path_to_image}")

def add_registration_logo(path_to_image):
    # This function remains the same as your original
    pass # (Your original logo code would go here)

# --- Shared Database & Helper Utilities (Receive Secrets) ---
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

def email_exists_in_users(email_to_check, secrets):
    conn = get_db_connection(secrets)
    if not conn: return True # Fail safe
    try:
        with conn.cursor() as cursor:
            query = "SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s"
            cursor.execute(query, (email_to_check.strip().lower(),))
            return cursor.fetchone()[0] > 0
    except Error as e:
        logging.error(f"DB Error checking email existence: {e}")
        return True # Fail safe
    finally:
        if conn and conn.is_connected(): conn.close()

def insert_admin_and_team_members(admin_data, password, team_emails, secrets):
    conn = get_db_connection(secrets)
    if not conn: return False
    try:
        with conn.cursor() as cursor:
            # Insert Admin User
            user_query = """
                INSERT INTO user_registration (
                    first_name, last_name, date_of_birth, age, gender, city, country,
                    organisation_level, organisation_name, designation, sports_team, roles,
                    Email_Id, Password, is_admin
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            admin_args = admin_data + (hashed_password.decode('utf-8'),)
            cursor.execute(user_query, admin_args)

            # Insert Team Members
            if team_emails:
                team_query = "INSERT INTO admin_team_members (admin_email, team_member_email, organisation_name) VALUES (%s, %s, %s)"
                admin_email = admin_data[12]
                org_name = admin_data[8]
                team_data = [(admin_email, email, org_name) for email in team_emails]
                cursor.executemany(team_query, team_data)
        conn.commit()
        return True
    except Error as e:
        logging.error(f"DB Error during admin/team insertion: {e}")
        conn.rollback()
        st.error("A database error occurred during registration.")
        return False
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Admin Registration View ---
def render_admin_registration_view(navigate_to, secrets):
    st.markdown("<h1>Admin / Organisation Lead Registration</h1>", unsafe_allow_html=True)

    # Simplified session state management
    if 'reg_form_data' not in st.session_state:
        st.session_state.reg_form_data = {
            "first_name": "", "last_name": "", "email": "",
            "dob": datetime.date.today() - datetime.timedelta(days=365*25),
            "country": "Select Country", "city": "Select City",
            "org_level": "Select", "org_name": "", "designation": "Select",
            "team_emails": [""] * 8
        }
    
    data = st.session_state.reg_form_data

    with st.form("admin_registration_form"):
        st.markdown("### Personal Details")
        c1, c2 = st.columns(2)
        data['first_name'] = c1.text_input("First Name*", value=data['first_name'])
        data['last_name'] = c2.text_input("Last Name*", value=data['last_name'])
        data['email'] = st.text_input("Email ID* (This will be your Login ID)", value=data['email'])
        password = st.text_input("Create Password* (min 8 characters)", type="password")
        confirm_password = st.text_input("Confirm Password*", type="password")
        
        st.markdown("### Organisation Details")
        data['org_name'] = st.text_input("Your Organisation Name*", value=data['org_name'])

        st.markdown("### Team Member Emails* (All 8 are Mandatory)")
        team_cols = st.columns(2)
        for i in range(8):
            data['team_emails'][i] = team_cols[i % 2].text_input(f"Team Member {i+1} Email*", value=data['team_emails'][i], key=f"tm_email_{i}")

        submitted = st.form_submit_button("Confirm & Invite Team")

    if submitted:
        # --- Start Validation ---
        errors = []
        if not data['first_name'] or not data['last_name']: errors.append("First and Last Name are required.")
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", data['email']):
            errors.append("A valid Admin Email is required.")
        elif email_exists_in_users(data['email'], secrets):
            errors.append(f"The email '{data['email']}' is already registered.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_password: errors.append("Passwords do not match.")
        if not data['org_name']: errors.append("Organisation Name is required.")
        
        unique_emails = {data['email'].lower()}
        valid_team_emails = []
        for i, email in enumerate(data['team_emails']):
            if not email:
                errors.append(f"Team Member {i+1} Email is mandatory.")
                continue
            email_lower = email.lower()
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_lower):
                errors.append(f"Team Member {i+1} Email '{email}' has an invalid format.")
            elif email_lower in unique_emails:
                errors.append(f"Team Member {i+1} Email '{email}' is a duplicate.")
            else:
                unique_emails.add(email_lower)
                valid_team_emails.append(email_lower)
        
        if len(valid_team_emails) != 8 and not any("mandatory" in e for e in errors):
            errors.append("Please provide 8 unique and valid team member emails.")
        # --- End Validation ---

        if errors:
            for error in errors:
                st.error(f"⚠️ {error}")
        else:
            # Prepare data for DB insertion
            dob_str = data['dob'].strftime('%Y-%m-%d')
            age = (datetime.date.today() - data['dob']).days // 365
            admin_data_for_db = (
                data['first_name'], data['last_name'], dob_str, age, "Not Specified",
                None, None, "Not Specified", data['org_name'], "Admin", None, "Admin", data['email'].lower()
            )
            
            if insert_admin_and_team_members(admin_data_for_db, password, valid_team_emails, secrets):
                st.success("✅ Admin registration successful! Team members will be invited.")
                st.balloons()
                # Clear form data from session state
                del st.session_state.reg_form_data
                del st.session_state.registration_choice
                navigate_to('login')
                st.rerun()

    if st.button("Cancel and Go to Login"):
        # Clear form data from session state
        if 'reg_form_data' in st.session_state: del st.session_state.reg_form_data
        if 'registration_choice' in st.session_state: del st.session_state.registration_choice
        navigate_to('login')
        st.rerun()


# --- Main Entry Point for This File ---
def user_registration_entrypoint(navigate_to, secrets):
    """
    Main entry point called by main.py router.
    Args:
        navigate_to (function): Callback function to switch pages.
        secrets (dict): Dictionary containing the application secrets.
    """
    set_registration_background(BG_IMAGE_PATH)
    add_registration_logo(LOGO_IMAGE_PATH)

    if "registration_choice" not in st.session_state:
        st.session_state.registration_choice = None
    
    if st.session_state.registration_choice is None:
        st.markdown("<h1>Choose Your Registration Type</h1>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("Sign up as Admin / Organisation Lead", use_container_width=True):
            st.session_state.registration_choice = "admin"
            st.rerun()
        if c2.button("Sign up as Team Member / Athlete", use_container_width=True):
            st.error("Team member registration is not yet implemented in this view.")
        if c3.button("Sign up as Consultant", use_container_width=True):
            st.error("Consultant registration is not yet implemented in this view.")
    
    elif st.session_state.registration_choice == "admin":
        render_admin_registration_view(navigate_to, secrets)
