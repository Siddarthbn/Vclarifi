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

# --- Import shared styling, background, logo functions and paths ---
try:
    from user_registration import (
        set_registration_background,
        add_registration_logo,
        apply_registration_custom_styles,
        BG_IMAGE_PATH as MAIN_BG_IMAGE_PATH,
        LOGO_IMAGE_PATH as MAIN_LOGO_IMAGE_PATH
    )
    SHARED_STYLES_LOADED = True
    logging.info("Shared styling from user_registration.py loaded successfully.")
except ImportError:
    st.warning("Could not import shared styling from user_registration.py. Consultant page may have basic styles.")
    logging.warning("Could not import shared styling from user_registration.py. Using fallbacks.")
    SHARED_STYLES_LOADED = False
    MAIN_BG_IMAGE_PATH = "images/background.jpg" # Example fallback
    MAIN_LOGO_IMAGE_PATH = "images/vtara.png"     # Example fallback


PREDEFINED_COUNTRIES = ["Select Country", "India", "Australia"]
COUNTRY_CITIES_MAP = {
    "India": ["Select City", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"],
    "Australia": ["Select City", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
}
GENERIC_CITY_LIST = ["Select City"]

AREAS_OF_EXPERTISE = [
    "Sports Psychology", "Physiotherapy", "Strength & Conditioning",
    "Sports Nutrition", "Data Analytics (Sports)", "Sports Management",
    "Technical Coaching", "Tactical Analysis", "Sports Medicine", "Other"
]
AVAILABILITY_OPTIONS = ["Select Availability", "Full-time", "Part-time", "Project-based (Freelance)"]

def get_db_connection():
    """Establishes and returns a MySQL database connection using st.secrets."""
    try:
        connection = mysql.connector.connect(
            host=st.secrets.database.DB_HOST,
            database=st.secrets.database.DB_DATABASE,
            user=st.secrets.database.DB_USER,
            password=st.secrets.database.DB_PASSWORD
        )
        return connection
    except (AttributeError, KeyError):
        st.error("Database credentials are not configured in your secrets file.")
        logging.error("Database secrets missing from .streamlit/secrets.toml.")
        return None
    except Error as e:
        st.error(f"Database Connection Error: {e}. Please check credentials and server status.")
        logging.error(f"Database Connection Error: {e}")
        return None

def email_exists_in_users(email):
    """Checks if an email already exists in the user_registration table."""
    connection = get_db_connection()
    if not connection:
        return True # Fails safe
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s", (email.lower(),))
        result = cursor.fetchone()
        exists = result[0] > 0 if result else False
        return exists
    except Error as e:
        st.error(f"Database Error (checking email existence): {e}")
        logging.error(f"Database Error checking email existence for {email.lower()}: {e}")
        return True # Fails safe
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()

def basic_consultant_styles_fallback():
    """Provides basic styling if shared styles cannot be loaded."""
    st.markdown("""
    <style>
        body { font-family: sans-serif; }
        .stApp {
            background-color: #2E4053;
            color: white;
        }
        h1, h2, h3, h4, h5, h6, p, label, div {
            color: white !important;
        }
        .stTextInput > div > input, .stTextArea > div > textarea, .stDateInput > div > input, .stNumberInput > div > input {
            color: #333 !important;
            background-color: #f0f2f6 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    st.info("Using fallback styles for the page as shared styles could not be loaded.")

    if not SHARED_STYLES_LOADED:
        def _fb_set_bg(path):
            if not os.path.exists(path):
                st.warning(f"Fallback: Background image not found at {path}. Applying default color.")
                logging.warning(f"Fallback: Background image not found at {path}.")
            else:
                try:
                    with open(path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode()
                    st.markdown(
                        f"""<style>.stApp {{ background-image: url("data:image/jpeg;base64,{encoded_string}"); background-size: cover; }}</style>""",
                        unsafe_allow_html=True)
                except Exception as e:
                    st.warning(f"Fallback: Could not load background image {path}: {e}. Applying default color.")
                    logging.error(f"Fallback: Could not load background image {path}: {e}")

        def _fb_add_logo(path):
            if not os.path.exists(path):
                st.warning(f"Fallback: Logo image not found at {path}. Displaying text logo.")
                logging.warning(f"Fallback: Logo image not found at {path}.")
                st.sidebar.title("VClarifi (Logo)")
            else:
                try:
                    st.sidebar.image(path, width=100)
                except Exception as e:
                    st.warning(f"Fallback: Could not load logo image {path}: {e}. Displaying text logo.")
                    logging.error(f"Fallback: Could not load logo image {path}: {e}")
                    st.sidebar.title("VClarifi (Logo)")

        _fb_set_bg(MAIN_BG_IMAGE_PATH)
        _fb_add_logo(MAIN_LOGO_IMAGE_PATH)

def is_valid_url(url):
    """Validates if the provided string is a basic valid URL (http/https/ftp)."""
    if not url: return True
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def is_valid_email_format(email_str):
    """Validates email format using a regular expression."""
    if not email_str: return False
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email_str.strip()) is not None

def insert_consultant_data(user_data_tuple, consultant_details_tuple, password):
    connection = get_db_connection()
    if not connection: return False
    db_success = False
    consultant_email = user_data_tuple[7].lower()

    if len(user_data_tuple) != 8:
        st.error(f"User data preparation error. Expected 8 elements, got {len(user_data_tuple)}.")
        logging.error(f"User data prep error for consultant: expected 8, got {len(user_data_tuple)}.")
        return False
    if len(consultant_details_tuple) != 8:
        st.error(f"Consultant details preparation error. Expected 8 professional detail elements, got {len(consultant_details_tuple)}.")
        logging.error(f"Consultant details prep error: expected 8, got {len(consultant_details_tuple)}.")
        return False
    cursor = None
    try:
        cursor = connection.cursor()
        user_query = """
            INSERT INTO user_registration (
                first_name, last_name, date_of_birth, age, gender, city, country, Email_Id,
                Password, is_admin, organisation_level, organisation_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
        """
        hashed_password_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user_data_list = list(user_data_tuple)
        user_data_list[7] = user_data_list[7].lower() # Standardize email
        organisation_level_value = "Consultant"
        organisation_name_value = "N/A" # Placeholder for consultants
        user_values_for_db = tuple(user_data_list) + \
                             (hashed_password_bytes.decode('utf-8'),
                              organisation_level_value,
                              organisation_name_value)
        cursor.execute(user_query, user_values_for_db)

        consultant_details_query = """
            INSERT INTO consultant_details (email_id, area_of_expertise, years_of_experience, certifications, bio, availability, preferred_sports_focus, linkedin_url, website_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        consultant_values_for_db = (consultant_email,) + consultant_details_tuple
        cursor.execute(consultant_details_query, consultant_values_for_db)
        connection.commit()
        db_success = True
        logging.info(f"Consultant {consultant_email} successfully registered in DB with org_level: '{organisation_level_value}', org_name: '{organisation_name_value}'.")
    except Error as e:
        st.error(f"Database Error during consultant registration: {e}")
        logging.error(f"Database Error during consultant registration for {consultant_email}: {e}")
        if connection and connection.is_connected():
            try:
                connection.rollback()
                logging.info(f"Transaction rolled back for consultant {consultant_email}.")
            except Error as rb_error:
                st.warning(f"Database rollback failed: {rb_error}")
                logging.error(f"Database rollback failed: {rb_error}")
    finally:
        if connection and connection.is_connected():
            if cursor: cursor.close()
            connection.close()
    return db_success

def send_consultant_registration_email(recipient_email, consultant_name):
    try:
        # Fetch secrets inside the function
        sender_email = st.secrets.email.SENDER_EMAIL
        sender_password = st.secrets.email.SENDER_APP_PASSWORD
        smtp_server = st.secrets.email.SMTP_SERVER
        smtp_port = st.secrets.email.SMTP_PORT
    except (AttributeError, KeyError):
        logging.critical("Email credentials not configured in st.secrets.")
        st.warning("Could not send registration email: Email service is not configured by the administrator.")
        return False
        
    subject = f"Welcome to VClarifi Network, {consultant_name}!"
    body = f"""Hello {consultant_name},\n\nWelcome to the VClarifi Network!\n\nYour registration as a Consultant is complete, and your profile has been successfully created.
You can access your consultant dashboard to manage your profile, update your availability, and showcase your expertise. We encourage you to keep your information current to attract relevant opportunities.
VClarifi is dedicated to connecting skilled professionals like you with sports teams and organizations seeking specialized knowledge. Based on your profile, teams may reach out to you for consultation opportunities directly through our platform.
Should you have any questions or require assistance, please do not hesitate to contact our support team.
We are excited to have you as part of the VClarifi network!

Sincerely,
The VClarifi Team"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
        logging.info(f"Consultant registration welcome email successfully sent to {recipient_email}.")
        return True
    except smtplib.SMTPAuthenticationError: logging.error(f"SMTP Authentication Error for {sender_email}. Check App Password.")
    except smtplib.SMTPServerDisconnected: logging.error("SMTP Server Disconnected unexpectedly.")
    except smtplib.SMTPConnectError: logging.error(f"Failed to connect to SMTP server {smtp_server}:{smtp_port}.")
    except Exception as e: logging.exception(f"An unexpected error occurred sending email to {recipient_email}: {e}")
    return False

def render_consultant_registration_view(main_app_navigate_to_function):
    if SHARED_STYLES_LOADED:
        set_registration_background(MAIN_BG_IMAGE_PATH)
        add_registration_logo(MAIN_LOGO_IMAGE_PATH)
        apply_registration_custom_styles()
    else:
        basic_consultant_styles_fallback()

    st.markdown("""<style>div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {background-color: #28a745 !important;color: white !important;font-weight: bold !important;border-radius: 8px !important;padding: 10px 20px !important;border: none !important;transition: background-color 0.3s ease, transform 0.1s ease;}div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {background-color: #218838 !important;transform: scale(1.02);}div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:active {transform: scale(0.98);}</style>""", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: white; margin-bottom: 20px;'>Consultant Registration</h1>", unsafe_allow_html=True)

    default_c_states = {
        "c_ui_dob": datetime.date(datetime.date.today().year - 25, 1, 1),
        "c_ui_country": PREDEFINED_COUNTRIES[0],
        "c_ui_city": GENERIC_CITY_LIST[0],
        "c_ui_expertise": [],
        "c_key_fn": "", "c_key_ln": "", "c_key_email": "",
        "c_key_age": 25, "c_key_gender": "Select",
        "c_key_exp": 0, "c_key_certs": "", "c_key_bio": "",
        "c_key_avail": AVAILABILITY_OPTIONS[0], "c_key_sfocus": "",
        "c_key_linkedin": "", "c_key_web": ""
    }
    for key, value in default_c_states.items():
        if key not in st.session_state: st.session_state[key] = value
    if "c_key_dob_widget_val" not in st.session_state:
        st.session_state.c_key_dob_widget_val = st.session_state.c_ui_dob

    if st.session_state.c_ui_country == PREDEFINED_COUNTRIES[0]: st.session_state.c_ui_city = "Select country first"
    elif st.session_state.c_ui_country in COUNTRY_CITIES_MAP:
        if st.session_state.c_ui_city not in COUNTRY_CITIES_MAP[st.session_state.c_ui_country]: st.session_state.c_ui_city = COUNTRY_CITIES_MAP[st.session_state.c_ui_country][0]
    else:
        if st.session_state.c_ui_city not in GENERIC_CITY_LIST: st.session_state.c_ui_city = GENERIC_CITY_LIST[0]

    with st.form("consultant_reg_form_main"):
        st.markdown("### Personal Details")
        col1_p, col2_p = st.columns(2)
        col1_p.text_input("First Name", key="c_key_fn")
        col2_p.text_input("Last Name", key="c_key_ln")
        st.text_input("Email ID", key="c_key_email", placeholder="example@domain.com")

        col1_pw, col2_pw = st.columns(2)
        c_form_pw_val_on_submit = col1_pw.text_input("Password (min 8 characters)", type="password", key="c_key_pw_form")
        c_form_cpw_val_on_submit = col2_pw.text_input("Confirm Password", type="password", key="c_key_cpw_form")

        col1_da, col2_da = st.columns(2)
        col1_da.date_input("Date of Birth", value=st.session_state.c_ui_dob,
                           min_value=datetime.date(1920, 1, 1),
                           max_value=datetime.date.today() - datetime.timedelta(days=365*18 + 4),
                           key="c_key_dob_widget_val")
        col2_da.number_input("Age", min_value=18, max_value=120, step=1, key="c_key_age")

        gender_options = ["Select", "Male", "Female", "Non-binary", "Prefer not to say"]
        st.selectbox("Gender", gender_options, key="c_key_gender", index=gender_options.index(st.session_state.c_key_gender))

        st.markdown("### Location Details")
        col1_l, col2_l = st.columns(2)
        col1_l.selectbox("Country", PREDEFINED_COUNTRIES, key="c_key_country_selector_widget", index=PREDEFINED_COUNTRIES.index(st.session_state.c_ui_country))

        _city_options_for_dropdown = GENERIC_CITY_LIST[:]
        _city_dropdown_disabled = True
        if st.session_state.c_ui_country == PREDEFINED_COUNTRIES[0]: _city_options_for_dropdown = ["Select country first"]
        elif st.session_state.c_ui_country in COUNTRY_CITIES_MAP:
            _city_options_for_dropdown = COUNTRY_CITIES_MAP[st.session_state.c_ui_country]
            _city_dropdown_disabled = False
        else: _city_dropdown_disabled = False

        _city_idx_for_widget = 0
        if st.session_state.c_ui_city in _city_options_for_dropdown: _city_idx_for_widget = _city_options_for_dropdown.index(st.session_state.c_ui_city)
        else: st.session_state.c_ui_city = _city_options_for_dropdown[0]

        col2_l.selectbox("City", _city_options_for_dropdown, key="c_key_city_selector_widget", index=_city_idx_for_widget, disabled=_city_dropdown_disabled)

        st.markdown("### Professional Details")
        st.multiselect("Area(s) of Expertise", AREAS_OF_EXPERTISE, key="c_key_expertise_selector_widget", default=st.session_state.c_ui_expertise)
        st.number_input("Years of Experience", min_value=0, max_value=60, step=1, key="c_key_exp")
        st.text_area("Certifications/Qualifications (Optional, comma-separated)", height=100, key="c_key_certs")
        st.text_area("Brief Bio/Profile Summary (max 1000 chars, Optional)", max_chars=1000, height=150, key="c_key_bio")
        st.selectbox("Availability", AVAILABILITY_OPTIONS, key="c_key_avail", index=AVAILABILITY_OPTIONS.index(st.session_state.c_key_avail))
        st.text_area("Preferred Sports Focus (Optional)", height=75, key="c_key_sfocus")

        st.markdown("#### Optional Links")
        st.text_input("LinkedIn Profile URL (Optional)", key="c_key_linkedin", placeholder="https://linkedin.com/in/yourprofile")
        st.text_input("Website/Portfolio URL (Optional)", key="c_key_web", placeholder="https://yourwebsite.com")
        st.markdown("---")
        c_submitted_button = st.form_submit_button("Confirm Consultant Registration")

    rerun_flag = False
    if st.session_state.c_key_dob_widget_val != st.session_state.c_ui_dob:
        st.session_state.c_ui_dob = st.session_state.c_key_dob_widget_val; rerun_flag = True
    if st.session_state.c_key_country_selector_widget != st.session_state.c_ui_country:
        st.session_state.c_ui_country = st.session_state.c_key_country_selector_widget
        if st.session_state.c_ui_country == PREDEFINED_COUNTRIES[0]: st.session_state.c_ui_city = "Select country first"
        elif st.session_state.c_ui_country in COUNTRY_CITIES_MAP: st.session_state.c_ui_city = COUNTRY_CITIES_MAP[st.session_state.c_ui_country][0]
        else: st.session_state.c_ui_city = GENERIC_CITY_LIST[0]
        rerun_flag = True
    if not _city_dropdown_disabled and st.session_state.c_key_city_selector_widget != st.session_state.c_ui_city:
        st.session_state.c_ui_city = st.session_state.c_key_city_selector_widget; rerun_flag = True
    if st.session_state.c_key_expertise_selector_widget != st.session_state.c_ui_expertise:
        st.session_state.c_ui_expertise = st.session_state.c_key_expertise_selector_widget; rerun_flag = True
    if rerun_flag: st.rerun()

    if c_submitted_button:
        s = st.session_state
        first = s.c_key_fn.strip()
        last = s.c_key_ln.strip()
        email = s.c_key_email.strip().lower()
        password = c_form_pw_val_on_submit
        confirm_pw = c_form_cpw_val_on_submit

        dob_val = s.c_key_dob_widget_val
        age = s.c_key_age
        gender = s.c_key_gender
        country_val = s.c_ui_country
        city_val = s.c_ui_city
        expertise_list = s.c_ui_expertise
        expertise_str = ", ".join(expertise_list) if expertise_list else None
        experience = s.c_key_exp
        certifications = s.c_key_certs.strip()
        bio = s.c_key_bio.strip()
        availability = s.c_key_avail
        sports_focus = s.c_key_sfocus.strip()
        linkedin = s.c_key_linkedin.strip()
        website = s.c_key_web.strip()

        errors = []
        if not first: errors.append("First Name is required.")
        if not last: errors.append("Last Name is required.")
        if not email or not is_valid_email_format(email): errors.append("A valid Email ID is required.")
        elif email_exists_in_users(email): errors.append(f"The email '{email}' is already registered.")
        if not password or len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_pw: errors.append("Passwords do not match.")
        today = datetime.date.today()
        try:
            calculated_age = today.year - dob_val.year - ((today.month, today.day) < (dob_val.month, dob_val.day))
            if calculated_age != age: errors.append(f"Entered Age ({age}) does not match DOB's age ({calculated_age}).")
        except AttributeError: errors.append("Invalid Date of Birth.")
        if age < 18: errors.append("Minimum age is 18.")
        if gender == "Select": errors.append("Gender is required.")
        if country_val == "Select Country": errors.append("Country is required.")
        if country_val != "Select Country" and city_val in ["Select City", "Select country first"]: errors.append("City is required.")
        if not expertise_list: errors.append("Area of Expertise is required.")
        if experience is None or experience < 0: errors.append("Years of Experience must be non-negative.")
        if availability == "Select Availability": errors.append("Availability is required.")
        if linkedin and not is_valid_url(linkedin): errors.append("Invalid LinkedIn URL.")
        if website and not is_valid_url(website): errors.append("Invalid Website URL.")

        if errors:
            for e_msg in errors: st.error(f"⚠️ {e_msg}")
        else:
            city_to_db = city_val if city_val not in ["Select City", "Select country first"] else None
            country_to_db = country_val if country_val != "Select Country" else None
            dob_str = dob_val.strftime('%Y-%m-%d')
            user_data_for_db = (first, last, dob_str, age, gender, city_to_db, country_to_db, email)
            consultant_prof_details_for_db = (expertise_str, experience, certifications or None, bio or None, availability, sports_focus or None, linkedin or None, website or None)

            if insert_consultant_data(user_data_for_db, consultant_prof_details_for_db, password):
                consultant_full_name = f"{first} {last}"
                st.success("Welcome to Vclarifi Network!")
                
                email_sent_status = send_consultant_registration_email(email, consultant_full_name)
                if email_sent_status:
                    logging.info(f"Welcome email successfully sent to consultant {email}.")
                else:
                    logging.warning(f"Consultant registration for {email} was successful, BUT welcome email FAILED to send. This was not shown to the user.")
                
                st.session_state.login_success_message = f"Consultant {email} registered. Please log in."
                keys_to_clear = [k for k in st.session_state if k.startswith("c_key_") or k.startswith("c_ui_")]
                for key_to_del in keys_to_clear:
                    if key_to_del in st.session_state: del st.session_state[key_to_del]
                if 'registration_choice' in st.session_state: del st.session_state['registration_choice']
                main_app_navigate_to_function('login')
                st.rerun()
            else:
                # FIX for SYNTAX ERROR: The original complex line was removed and simplified.
                st.error("❌ Consultant registration failed. Please review details or contact support.")


    if st.button("Back to Login", key="consultant_back_to_login_btn", use_container_width=True):
        keys_to_clear = [k for k in st.session_state if k.startswith("c_key_") or k.startswith("c_ui_")]
        for key_to_del in keys_to_clear:
            if key_to_del in st.session_state: del st.session_state[key_to_del]
        if 'registration_choice' in st.session_state: del st.session_state['registration_choice']
        main_app_navigate_to_function('login')
        st.rerun()

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Consultant Registration - VClarifi")
    if '_stcore_dg_messages' not in st.session_state:
        st.session_state._stcore_dg_messages = []

    def mock_navigate(page_name):
        st.toast(f"Mock navigation to: {page_name}")
        if page_name == 'login' and st.session_state.get('login_success_message'):
            st.info(f"INFO: Nav to Login. Msg: {st.session_state.login_success_message}")
        logging.info(f"Mock navigation to: {page_name}")
    st.sidebar.info("Standalone run: Consultant Registration")
    render_consultant_registration_view(mock_navigate)