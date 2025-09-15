import streamlit as st
import datetime
import base64
import mysql.connector
from mysql.connector import Error
import bcrypt
import re  # Ensure re is imported
import logging
import smtplib
import boto3
import os
from email.mime.text import MIMEText

# Assuming user_registration_2.py exists or is mocked as in your __main__
import user_registration_2
# import consultant_registration # This will be handled by try-except in the entrypoint

# --- Logging Configuration ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# --- BEGIN SHARED CONFIGURATION AND UTILS ---
BG_IMAGE_PATH = "C:/Users/DELL/Desktop/background.jpg" # Ensure this path is correct for your system
LOGO_IMAGE_PATH = "C:/Users/DELL/Desktop/VTARA.png"    # Ensure this path is correct for your system

# --- AWS SECRETS MANAGER HELPER FUNCTION ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    """
    Fetches application secrets from AWS Secrets Manager and caches them.
    It expects the secret to be a single JSON object.
    """
    secret_name = "production/vclarifi/secrets"  # The name of your secret
    region_name = os.environ.get("AWS_REGION", "us-east-1") # Use env var or default

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        # Get the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        return json.loads(secret_string)
    except Exception as e:
        # Handle exceptions gracefully
        st.error(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        return None

# --- GET SECRETS ---
secrets = get_aws_secrets()

# Check if secrets were loaded successfully
if secrets:
    # --- DATABASE CONFIGURATION ---
    database_secrets = secrets.get("database", {})
    DB_HOST = database_secrets.get("DB_HOST")
    DB_DATABASE = database_secrets.get("DB_DATABASE")
    DB_USER = database_secrets.get("DB_USER")
    DB_PASSWORD = database_secrets.get("DB_PASSWORD")
    # A port value might not be in the secret, so provide a default
    DB_PORT = database_secrets.get("DB_PORT", 3306)

    # --- EMAIL CONFIGURATION ---
    email_secrets = secrets.get("email", {})
    SENDER_EMAIL = email_secrets.get("SENDER_EMAIL")
    SENDER_APP_PASSWORD = email_secrets.get("SENDER_APP_PASSWORD")
    SMTP_SERVER = email_secrets.get("SMTP_SERVER")
    SMTP_PORT = email_secrets.get("SMTP_PORT")
else:
    st.warning("Could not load secrets. Check the AWS Secrets Manager configuration and permissions.")

PREDEFINED_COUNTRIES = ["Select Country", "India", "Australia"]
COUNTRY_CITIES_MAP = {
    "India": ["Select City", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"],
    "Australia": ["Select City", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
}
GENERIC_CITY_LIST = ["Select City"]

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST, database=DB_DATABASE, user=DB_USER, password=DB_PASSWORD
        )
        return connection
    except Error as e:
        st.error(f"Database Connection Error. Please ensure the database is running and credentials are correct.")
        logging.error(f"Database Connection Error: {e}")
        return None

def calculate_age_from_dob(birth_date):
    today = datetime.date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def is_valid_email_format(email_str):
    if not email_str: return False
    # Basic regex for email validation (adjust if more complex rules are needed)
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email_str) is not None

def email_exists_in_users(email_to_check):
    connection = get_db_connection()
    if not connection:
        st.error("Database not connected. Cannot verify email uniqueness at this time.")
        logging.warning("DB not connected during email_exists_in_users check.")
        return True # Fail safe; prevent registration if DB cannot be checked

    cursor = None
    processed_email = email_to_check.strip().lower()
    try:
        cursor = connection.cursor()
        query = "SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s"
        logging.debug(f"Executing Query: {query} with params: ({processed_email},)")
        cursor.execute(query, (processed_email,))
        count = cursor.fetchone()[0]
        logging.debug(f"Email check for {processed_email}: found {count} occurrences.")
        return count > 0
    except Error as e:
        st.error(f"DB Error (while checking email existence). Please try again.")
        logging.error(f"DB Error checking email existence for {processed_email}: {e}")
        return True # Fail safe
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()

def set_registration_background(path_to_image):
    if not os.path.exists(path_to_image):
        st.warning(f"Background image not found: {path_to_image}. Applying default background.")
        logging.warning(f"Background image not found: {path_to_image}")
        st.markdown("""<style>[data-testid="stAppViewContainer"] { background-color: #223344; color: white;}</style>""", unsafe_allow_html=True)
        return
    try:
        with open(path_to_image, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpeg;base64,{encoded}");
                background-size: cover; background-position: center; background-attachment: fixed;
                color: white !important;
            }}
            [data-testid="stHeader"], [data-testid="stToolbar"] {{
                background: transparent !important;
            }}
            [data-testid="stAppViewContainer"] p,
            [data-testid="stAppViewContainer"] label,
            [data-testid="stAppViewContainer"] h1,
            [data-testid="stAppViewContainer"] h2,
            [data-testid="stAppViewContainer"] h3,
            [data-testid="stAppViewContainer"] li
             {{
                color: white !important;
            }}
            </style>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error setting background image. Applying default.")
        logging.error(f"Error setting background image: {e}")
        st.markdown("""<style>[data-testid="stAppViewContainer"] { background-color: #223344; color: white;}</style>""", unsafe_allow_html=True)

def add_registration_logo(path_to_image):
    text_logo_html = f"""
        <div style='position: fixed; top: 25px; right: 30px; display: flex; align-items: center; gap: 12px; z-index: 10000 !important;'>
            <span style='color: white; font-size: 26px; font-weight: bold; font-family: Arial, sans-serif; text-shadow: 1px 1px 2px rgba(0,0,0,0.4);'>VCLARIFI</span>
        </div>"""
    if not os.path.exists(path_to_image):
        st.warning(f"Logo image not found: {path_to_image}. Text logo will be used.")
        logging.warning(f"Logo image not found: {path_to_image}")
        st.markdown(text_logo_html, unsafe_allow_html=True)
        return
    try:
        with open(path_to_image, "rb") as logo_file:
            encoded = base64.b64encode(logo_file.read()).decode()
        st.markdown(f"""
            <div style='position: fixed; top: 25px; right: 30px; display: flex; align-items: center; gap: 12px; z-index: 10000 !important;'>
                <img src="data:image/png;base64,{encoded}" width="60" style="filter: drop-shadow(0px 1px 2px rgba(0,0,0,0.3));" alt="VClarifi Logo">
                <span style='color: white; font-size: 26px; font-weight: bold; font-family: Arial, sans-serif; text-shadow: 1px 1px 2px rgba(0,0,0,0.4);'>VCLARIFI</span>
            </div>""", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying logo image. Using text logo.")
        logging.error(f"Error displaying logo image: {e}")
        st.markdown(text_logo_html, unsafe_allow_html=True)

def apply_registration_custom_styles():
    st.markdown("""
        <style>
        .stTextInput > label, .stDateInput > label, .stSelectbox > label, .stNumberInput > label,
        .stCheckbox > label > span, .stRadio > label > span, .stTextArea > label,
        .stFileUploader > label, .stMultiSelect > label {
            color: white !important;
            font-weight: bold !important;
            margin-bottom: 5px !important;
        }
        .stTextInput input, .stDateInput input, .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div,
        .stTextArea textarea {
            background-color: rgba(255, 255, 255, 0.9) !important;
            color: black !important;
            border: 1px solid #ced4da !important;
            box-shadow: none !important;
            border-radius: 6px !important;
            font-size: 1rem !important;
        }
        /* General button style (e.g. for Cancel, registration type choices) */
        .stButton>button, div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
            width: 100%;
            padding: 12px 20px !important;
            font-size: 16px !important;
            border-radius: 8px !important;
            background-color: #2c662d !important; /* Maintained green for general buttons */
            color: white !important;
            border: none !important;
            font-weight: bold !important;
            transition: background-color 0.2s ease, transform 0.1s ease;
        }
        .stButton>button:hover, div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #1e4720 !important;
            transform: scale(1.01);
        }
        .stButton>button:active, div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:active {
            transform: scale(0.99);
        }
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li {
            color: white !important;
        }
        div[data-testid="stMarkdownContainer"] strong {
            color: white !important;
        }
        div[data-testid="stMarkdownContainer"] > h1 {
            text-align: center;
            margin-bottom: 25px !important;
            font-size: 2.5rem !important;
            color: white !important;
        }
         div[data-testid="stMarkdownContainer"] > h3 {
            margin-top: 1.5rem !important;
            margin-bottom: 0.8rem !important;
            color: white !important;
        }
        .stAlert p {
            color: #000000 !important; /* Ensure alert text is readable */
        }
        .stSelectbox > div[data-baseweb="select"] { width: 100% !important; }
        </style>""", unsafe_allow_html=True)
# --- END SHARED CONFIGURATION AND UTILS ---

# --- EMAIL SENDING FUNCTIONS ---
def _send_email_generic(recipient_email, subject, body, email_type_for_log="Generic"):
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
        logging.critical(f"{email_type_for_log} Email sending misconfiguration: SENDER_EMAIL or SENDER_APP_PASSWORD is not set.")
        return False

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email
    
    email_sent_successfully_flag = False
    server_instance = None

    try:
        logging.debug(f"Attempting SMTP_SSL connection for {email_type_for_log} to {recipient_email}...")
        server_instance = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        # server_instance.set_debuglevel(1) # UNCOMMENT FOR VERY VERBOSE SMTP LOGS TO TERMINAL
        logging.debug(f"SMTP_SSL Connected for {email_type_for_log}. Attempting login...")
        server_instance.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        logging.debug(f"Logged in as {SENDER_EMAIL} for {email_type_for_log}. Attempting to send email...")
        server_instance.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        email_sent_successfully_flag = True
        logging.info(f"{email_type_for_log} email successfully handed to sendmail for {recipient_email}.")
    except smtplib.SMTPAuthenticationError:
        logging.exception(f"SMTP Authentication Error for {email_type_for_log} to {recipient_email}. Check App Password.")
    except smtplib.SMTPServerDisconnected:
        logging.exception(f"SMTPServerDisconnected for {email_type_for_log} to {recipient_email}.")
    except smtplib.SMTPConnectError:
        logging.exception(f"SMTPConnectError for {email_type_for_log} to {recipient_email} ({SMTP_SERVER}:{SMTP_PORT}).")
    except ConnectionRefusedError:
        logging.exception(f"ConnectionRefusedError for {email_type_for_log} to {recipient_email} ({SMTP_SERVER}:{SMTP_PORT}).")
    except TimeoutError:
        logging.exception(f"TimeoutError for {email_type_for_log} to {recipient_email} ({SMTP_SERVER}:{SMTP_PORT}).")
    except OSError as e:
        logging.exception(f"OSError for {email_type_for_log} to {recipient_email}: {e}. Email sent status: {email_sent_successfully_flag}")
    except Exception as e:
        logging.exception(f"Unexpected error sending {email_type_for_log} email to {recipient_email}: {e}. Email sent status: {email_sent_successfully_flag}")
    finally:
        if server_instance:
            try:
                logging.debug(f"Attempting to quit server for {email_type_for_log}...")
                server_instance.quit()
                logging.debug(f"Server quit successfully for {email_type_for_log}.")
            except smtplib.SMTPServerDisconnected:
                 logging.warning(f"Server was already disconnected during quit for {email_type_for_log}.")
            except Exception as e_quit:
                 logging.error(f"Error during SMTP server_instance.quit() for {email_type_for_log}: {e_quit}")
        logging.debug(f"Exiting _send_email_generic for {email_type_for_log} to {recipient_email}. Sent flag: {email_sent_successfully_flag}")
    return email_sent_successfully_flag


def send_admin_registration_email(admin_email, admin_name, organisation_name):
    subject = f"Welcome to VClarifi, {admin_name}! Your Admin Account for '{organisation_name}' is Active"
    body = f"""Hello {admin_name},\n\nCongratulations! Your administrator account for '{organisation_name}' on VClarifi has been successfully registered.\n\nYou now have access to your VClarifi dashboard where you can:\n- Manage your organisation's profile.\n- Notify your invited team members to take their surveys.\n- View the consolidated survey dashboard once your team members have completed their surveys.\n- Access insights and recommendations based on the survey data.\n\nWe encourage you to log in and familiarize yourself with the platform.\n\nIf you have any questions, please contact our support team.\n\nBest regards,\nThe VClarifi Team"""
    return _send_email_generic(admin_email, subject, body, "Admin Welcome")

def send_team_member_invitation_email(team_member_email, admin_name, organisation_name):
    survey_link = "https://vclarifiapp.com" # TODO: Replace with actual/dynamic survey link if needed
    subject = f"Invitation to take a survey for '{organisation_name}' on VClarifi"
    body = f"""Hello,\n\nYou have been invited by {admin_name} from '{organisation_name}' to participate in a survey on the VClarifi platform.\n\nYour input is valuable. Please click the link below to access and complete the survey:\n{survey_link}\n\nIf you have any questions regarding this invitation or the survey, please contact your organisation's administrator ({admin_name}).\n\nThank you for your participation!\n\nBest regards,\nThe VClarifi Team"""
    return _send_email_generic(team_member_email, subject, body, "Team Member Invitation")

# --- Admin Specific Functions ---
def insert_admin_and_team_members(admin_data_tuple, password, team_member_emails_list):
    connection = get_db_connection()
    if not connection: return False
    
    db_processing_successful = False
    # admin_data_tuple elements: (first_name, last_name, dob, age, gender, city, country,
    #                             org_level, org_name, designation, sports_team, roles, Email_Id)
    admin_email_raw = admin_data_tuple[12] # Email_Id is the 13th element (index 12)
    admin_email = admin_email_raw.strip().lower()
    admin_org_name = admin_data_tuple[8] # organisation_name is the 9th element (index 8)
    cursor = None
    
    try:
        cursor = connection.cursor()
        
        # ==============================================================================
        # CRITICAL POINT FOR DATABASE ERROR 1054 (Unknown column 'is_team_member')
        # ==============================================================================
        # The user_query string below DOES NOT include 'is_team_member'.
        # If you are getting an error about 'is_team_member', it means the query
        # string in YOUR ACTUAL LOCAL .PY FILE that is running is DIFFERENT from this.
        #
        # ACTION: 
        # 1. Run your Streamlit app.
        # 2. When the error occurs, CHECK YOUR TERMINAL/CONSOLE for log messages.
        # 3. Find the log line: "DEBUG: Executing Query (user_registration): INSERT INTO user_registration..."
        # 4. That log line shows the EXACT query being sent to the database. Compare it carefully to the 'user_query' string below.
        # 5. If the logged query in your terminal INCLUDES 'is_team_member' in the column list
        #    (e.g., ... Email_Id, Password, is_admin, is_team_member), then you must
        #    EDIT YOUR LOCAL .PY FILE to remove 'is_team_member' from the column list of the INSERT statement
        #    AND remove its corresponding '%s' placeholder from the VALUES part if it had one.
        #
        # The 'user_query' as defined here is correct if your `user_registration` table
        # has the 15 columns listed (first_name...is_admin) and 'is_team_member' is NOT one of them.
        # ==============================================================================
        user_query = """
            INSERT INTO user_registration (
                first_name, last_name, date_of_birth, age, gender, city, country,
                organisation_level, organisation_name, designation, sports_team, roles,
                Email_Id, Password, is_admin
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        """
        # This query expects 14 values to be provided in the `args_for_admin_insert` tuple.
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        if len(admin_data_tuple) != 13:
            st.error("Internal data error: Admin information is incomplete for database record.")
            logging.error(f"Admin data preparation error: expected 13 user fields for admin_data_tuple, got {len(admin_data_tuple)}.")
            return False
        
        admin_data_list_for_insert = list(admin_data_tuple)
        admin_data_list_for_insert[12] = admin_email # Ensure the Email_Id used in the tuple is the processed one
        final_admin_tuple_for_insert = tuple(admin_data_list_for_insert)
        
        # final_admin_tuple_for_insert (13 elements) + hashed_password (1 element) = 14 arguments
        args_for_admin_insert = final_admin_tuple_for_insert + (hashed_password.decode('utf-8'),)

        logging.debug("--- Admin User Registration Insert (Attempting) ---")
        logging.debug(f"Executing Query (user_registration): {user_query}") # <<< EXAMINE THIS LOG IN YOUR TERMINAL
        logging.debug(f"Number of placeholders in query: {user_query.count('%s')}")
        logging.debug(f"Number of arguments provided: {len(args_for_admin_insert)}")
        logging.debug(f"Arguments for admin insert: {args_for_admin_insert}")
        
        if user_query.count('%s') != len(args_for_admin_insert):
            # This is a critical internal error if it happens, means logic mismatch
            critical_msg = (f"CRITICAL INTERNAL ERROR: Mismatch between SQL query placeholders ({user_query.count('%s')}) "
                            f"and arguments provided ({len(args_for_admin_insert)}) for admin user registration. "
                            f"This should not happen if admin_data_tuple length check is correct.")
            logging.critical(critical_msg)
            st.error("A critical internal error occurred during registration. Please contact support. (Code: ARG_MISMATCH)")
            # Ensure rollback and connection closure if we were to return early
            if connection and connection.is_connected():
                try: connection.rollback()
                except Error as rb_err: logging.error(f"Rollback failed after critical mismatch: {rb_err}")
            return False # Stop further processing

        cursor.execute(user_query, args_for_admin_insert)
        logging.info(f"Admin user {admin_email} inserted into user_registration.")
        
        if team_member_emails_list:
            team_member_query = """
                INSERT INTO admin_team_members (admin_email, team_member_email, organisation_name)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE organisation_name = VALUES(organisation_name) 
            """
            for team_email_processed_for_insert in team_member_emails_list:
                if team_email_processed_for_insert: 
                    try:
                        logging.debug(f"Inserting/Updating team member: {team_email_processed_for_insert} for admin {admin_email}")
                        cursor.execute(team_member_query, (admin_email, team_email_processed_for_insert, admin_org_name))
                    except mysql.connector.IntegrityError as ie_team:
                        st.warning(f"Could not fully process team member {team_email_processed_for_insert} for '{admin_org_name}'. Possible duplicate or data issue: {ie_team}")
                        logging.warning(f"Integrity error processing team member {team_email_processed_for_insert} by admin {admin_email} for org '{admin_org_name}': {ie_team}")
                    except Error as team_db_error: 
                        st.error(f"Error processing team member {team_email_processed_for_insert}: {team_db_error}")
                        logging.error(f"DB Error processing team member {team_email_processed_for_insert} by admin {admin_email} for org '{admin_org_name}': {team_db_error}")
        
        connection.commit()
        db_processing_successful = True
        logging.info(f"Admin {admin_email} and team members for {admin_org_name} successfully committed to DB.")

    except Error as main_db_error:
        st.error(f"Database operation failed during Admin/Team registration. Please try again or contact support if the issue persists.")
        logging.error(f"Main DB Error (Admin/Team Insertion) for admin {admin_email}: {main_db_error}. Review logged query and arguments.")
        if connection and connection.is_connected():
            try:
                connection.rollback()
                logging.info(f"Transaction rolled back for admin {admin_email} due to error: {main_db_error}")
            except Error as rb_err:
                logging.error(f"Database rollback attempt failed: {rb_err}")
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()
            logging.debug(f"Database connection closed for admin {admin_email} operation.")
            
    return db_processing_successful

# --- Admin Registration Form View ---
def render_admin_registration_view(main_app_navigate_to_function):
    # Specific style for the Admin form's submit button
    st.markdown(""" 
    <style>
        div[data-testid="stForm"][key="admin_registration_form_actual"] div[data-testid="stFormSubmitButton"] button {
            background-color: #28a745 !important; 
        }
        div[data-testid="stForm"][key="admin_registration_form_actual"] div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #218838 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center;'>Admin / Organisation Lead Registration</h1>", unsafe_allow_html=True)
    
    default_admin_states = {
        "admin_dob_ui": datetime.date(datetime.date.today().year - 25, 1, 1),
        "admin_country_ui": PREDEFINED_COUNTRIES[0],
        "admin_city_ui": GENERIC_CITY_LIST[0],
        "admin_org_level_ui": "Select",
        "admin_fn_form": "", "admin_ln_form": "", "admin_email_form": "", "admin_pw_form": "", "admin_cpw_form": "",
        "admin_gender_form": "Select",
        "admin_org_name_form": "",
        "admin_sport_focus_form": "Select", "admin_role_form": "Select", "admin_designation_form": "Select"
    }
    default_admin_states["admin_age_form"] = calculate_age_from_dob(default_admin_states["admin_dob_ui"])
    for i in range(8): default_admin_states[f"admin_team_email_{i}_form"] = ""

    for key, value in default_admin_states.items():
        if key not in st.session_state: st.session_state[key] = value
    
    country_selection = st.session_state.admin_country_ui
    if country_selection == PREDEFINED_COUNTRIES[0]:
        city_options_for_form = ["Select country first"]
        current_city_selection = city_options_for_form[0]
        city_dropdown_is_disabled = True
    else:
        city_options_for_form = COUNTRY_CITIES_MAP.get(country_selection, GENERIC_CITY_LIST[:])
        current_city_selection = st.session_state.admin_city_ui
        if current_city_selection not in city_options_for_form:
            current_city_selection = city_options_for_form[0]
        city_dropdown_is_disabled = False
    st.session_state.admin_city_ui = current_city_selection

    # Corrected st.form call
    with st.form(key="admin_registration_form_actual"):
        st.markdown("### Personal Details")
        col1_name, col2_name = st.columns(2)
        admin_fn_val = col1_name.text_input("First Name*", value=st.session_state.admin_fn_form, key="admin_fn_widget")
        admin_ln_val = col2_name.text_input("Last Name*", value=st.session_state.admin_ln_form, key="admin_ln_widget")
        admin_email_val = st.text_input("Email ID* (This will be your Admin Login ID)", value=st.session_state.admin_email_form, placeholder="your.email@example.com", key="admin_email_widget")
        
        col1_pass, col2_pass = st.columns(2)
        admin_pw_val = col1_pass.text_input("Create Password* (min 8 characters)", type="password", value=st.session_state.admin_pw_form, key="admin_pw_widget")
        admin_cpw_val = col2_pass.text_input("Confirm Password*", type="password", value=st.session_state.admin_cpw_form, key="admin_cpw_widget")
        
        col1_dob_age, col2_dob_age = st.columns(2)
        admin_dob_val = col1_dob_age.date_input("Date of Birth*",
                                        value=st.session_state.admin_dob_ui,
                                        min_value=datetime.date(1920, 1, 1),
                                        max_value=datetime.date.today() - datetime.timedelta(days=(365*18 + 4)), # Approx 18 years (accounts for some leap years)
                                        key="admin_dob_widget_actual")
        
        admin_age_val = col2_dob_age.number_input("Age (auto-calculated, min 18)*", 
                                        min_value=18, max_value=120, step=1, 
                                        value=st.session_state.admin_age_form, 
                                        key="admin_age_widget", disabled=True)

        gender_options = ["Select", "Male", "Female", "Non-binary", "Prefer not to say"]
        admin_gender_val = st.selectbox("Gender*", gender_options, 
                                    index=gender_options.index(st.session_state.admin_gender_form), 
                                    key="admin_gender_widget")
        
        st.markdown("### Location Details")
        col1_loc, col2_loc = st.columns(2)
        admin_country_val = col1_loc.selectbox("Country*", PREDEFINED_COUNTRIES,
                                            index=PREDEFINED_COUNTRIES.index(st.session_state.admin_country_ui),
                                            key="admin_country_widget_actual")

        admin_city_val = col2_loc.selectbox("City*", city_options_for_form,
                                        index=city_options_for_form.index(st.session_state.admin_city_ui),
                                        disabled=city_dropdown_is_disabled,
                                        key="admin_city_widget_actual")
        
        st.markdown("### Organisation Details")
        col1_org, col2_org = st.columns(2)
        org_level_options_list = ["Select", "National Sports Organisation", "State Sports Organisation", "Club", "Sports Company", "Sports Team", "School/University Team", "Other"]
        admin_org_level_val = col1_org.selectbox("Organisation Level*", org_level_options_list,
                                                index=org_level_options_list.index(st.session_state.admin_org_level_ui),
                                                key="admin_org_level_widget_actual")
        admin_org_name_val = col2_org.text_input("Your Organisation Name*", value=st.session_state.admin_org_name_form, key="admin_org_name_widget")
        
        current_org_level_for_display = st.session_state.admin_org_level_ui
        admin_sport_focus_val_form = st.session_state.admin_sport_focus_form # Use _form suffix for values from widgets before assignment
        admin_role_val_form = st.session_state.admin_role_form
        admin_designation_val_form = st.session_state.admin_designation_form

        if current_org_level_for_display in ["Sports Team", "School/University Team"]:
            st.markdown("#### Your Role in the Team")
            col1_sport_role, col2_sport_role = st.columns(2)
            sports_team_opts = ["Select", "Basketball", "Football (Soccer)", "Cricket", "Hockey", "Athletics", "Swimming", "Other"]
            admin_sport_focus_val_form = col1_sport_role.selectbox("Primary Sport Focus/Team Type*", sports_team_opts, 
                                                            index=sports_team_opts.index(st.session_state.admin_sport_focus_form), 
                                                            key="admin_sport_focus_widget")
            role_opts = ["Select", "Head Coach", "Team Manager", "Owner", "Director of Sports", "Captain", "Other"]
            admin_role_val_form = col2_sport_role.selectbox("Your Role in Organisation/Team*", role_opts, 
                                                    index=role_opts.index(st.session_state.admin_role_form), 
                                                    key="admin_role_widget")
        elif current_org_level_for_display not in ["Select", ""]:
            st.markdown("#### Your Designation")
            designation_opts = ["Select", "CEO", "President", "Director", "General Manager", "Secretary", "Head of Department", "Other"]
            admin_designation_val_form = st.selectbox("Your Designation*", designation_opts, 
                                                index=designation_opts.index(st.session_state.admin_designation_form), 
                                                key="admin_designation_widget")
            
        st.markdown("### Team Member Emails* (All 8 are Mandatory)")
        st.caption("Provide unique, valid email IDs for 8 team members you wish to invite. These cannot be the same as the admin's email.")
        cols_team_emails_form = st.columns(2)
        admin_team_emails_val_form = []
        for i in range(8):
            with cols_team_emails_form[i % 2]:
                admin_team_emails_val_form.append(st.text_input(f"Team Member {i+1} Email*", 
                                                        value=st.session_state.get(f"admin_team_email_{i}_form", ""), 
                                                        key=f"admin_team_email_{i}_widget"))
                
        st.markdown("---")
        submitted_admin_form_button = st.form_submit_button("Confirm Admin Registration & Invite Team")

    rerun_form_flag = False
    if admin_dob_val != st.session_state.admin_dob_ui:
        st.session_state.admin_dob_ui = admin_dob_val
        st.session_state.admin_age_form = calculate_age_from_dob(admin_dob_val)
        rerun_form_flag = True
    
    if admin_country_val != st.session_state.admin_country_ui:
        st.session_state.admin_country_ui = admin_country_val
        rerun_form_flag = True
        
    if not city_dropdown_is_disabled and admin_city_val != st.session_state.admin_city_ui :
        st.session_state.admin_city_ui = admin_city_val

    if admin_org_level_val != st.session_state.admin_org_level_ui:
        st.session_state.admin_org_level_ui = admin_org_level_val
        st.session_state.admin_sport_focus_form = "Select" # Reset dependent fields
        st.session_state.admin_role_form = "Select"
        st.session_state.admin_designation_form = "Select"
        rerun_form_flag = True

    st.session_state.admin_fn_form = admin_fn_val
    st.session_state.admin_ln_form = admin_ln_val
    st.session_state.admin_email_form = admin_email_val
    st.session_state.admin_pw_form = admin_pw_val
    st.session_state.admin_cpw_form = admin_cpw_val
    st.session_state.admin_gender_form = admin_gender_val
    st.session_state.admin_org_name_form = admin_org_name_val
    if current_org_level_for_display in ["Sports Team", "School/University Team"]:
        st.session_state.admin_sport_focus_form = admin_sport_focus_val_form
        st.session_state.admin_role_form = admin_role_val_form
    elif current_org_level_for_display not in ["Select", ""]:
        st.session_state.admin_designation_form = admin_designation_val_form
    for i in range(8):
        st.session_state[f"admin_team_email_{i}_form"] = admin_team_emails_val_form[i]

    if rerun_form_flag:
        st.rerun()

    if submitted_admin_form_button:
        first_name_submit = st.session_state.admin_fn_form.strip()
        last_name_submit = st.session_state.admin_ln_form.strip()
        email_submit = st.session_state.admin_email_form.strip().lower()
        password_submit = st.session_state.admin_pw_form
        confirm_pw_submit = st.session_state.admin_cpw_form
        dob_submit_obj = st.session_state.admin_dob_ui
        age_submit_val = st.session_state.admin_age_form
        gender_submit_val = st.session_state.admin_gender_form
        country_submit_val = st.session_state.admin_country_ui
        city_submit_val = st.session_state.admin_city_ui
        org_level_submit_val = st.session_state.admin_org_level_ui
        org_name_submit_val = st.session_state.admin_org_name_form.strip()
        sport_focus_submit_val = st.session_state.admin_sport_focus_form
        role_submit_val = st.session_state.admin_role_form
        designation_submit_val = st.session_state.admin_designation_form
        team_emails_submit_list_raw = [st.session_state.get(f"admin_team_email_{i}_form", "").strip() for i in range(8)]
        
        validation_errors = []
        if not first_name_submit: validation_errors.append("First Name is required.")
        if not last_name_submit: validation_errors.append("Last Name is required.")
        if not is_valid_email_format(email_submit):
            validation_errors.append("A valid Admin Email ID is required.")
        elif email_exists_in_users(email_submit):
            validation_errors.append(f"The Admin Email ID '{email_submit}' is already registered. Please use a different email or log in.")
        if not password_submit or len(password_submit) < 8: validation_errors.append("Password must be at least 8 characters long.")
        if password_submit != confirm_pw_submit: validation_errors.append("Passwords do not match.")
        if age_submit_val < 18 : validation_errors.append("Admin must be at least 18 years old.")
        if gender_submit_val == "Select": validation_errors.append("Gender selection is required.")
        if country_submit_val == "Select Country": validation_errors.append("Country selection is required.")
        if country_submit_val != "Select Country" and city_submit_val in ["Select City", "Select country first"]:
            validation_errors.append("City selection is required for the chosen country.")
        if org_level_submit_val == "Select": validation_errors.append("Organisation Level is required.")
        if not org_name_submit_val: validation_errors.append("Organisation Name is mandatory.")
            
        final_designation_for_db, final_sports_team_for_db, final_role_for_db = None, None, None
        if org_level_submit_val in ["Sports Team", "School/University Team"]:
            if sport_focus_submit_val == "Select": validation_errors.append("Primary Sport Focus/Team Type is required.")
            else: final_sports_team_for_db = sport_focus_submit_val
            if role_submit_val == "Select": validation_errors.append("Your Role in Organisation/Team is required.")
            else: final_role_for_db = role_submit_val
        elif org_level_submit_val not in ["Select", ""]:
            if designation_submit_val == "Select": validation_errors.append("Your Designation is required.")
            else: final_designation_for_db = designation_submit_val

        processed_team_emails_for_db = []
        all_submitted_emails_for_uniqueness = {email_submit}
        
        for i, tm_email_raw_submit in enumerate(team_emails_submit_list_raw):
            if not tm_email_raw_submit:
                validation_errors.append(f"Team Member {i+1} Email is mandatory."); continue
            tm_email_processed_submit = tm_email_raw_submit.lower()
            if not is_valid_email_format(tm_email_processed_submit):
                validation_errors.append(f"Team Member {i+1} Email '{tm_email_raw_submit}' has an invalid format."); continue
            if tm_email_processed_submit in all_submitted_emails_for_uniqueness:
                validation_errors.append(f"Team Member {i+1} Email '{tm_email_raw_submit}' is a duplicate of another provided email (admin or other team member)."); continue
            if email_exists_in_users(tm_email_processed_submit):
                validation_errors.append(f"Team Member {i+1} Email '{tm_email_raw_submit}' is already registered as a user."); continue
            processed_team_emails_for_db.append(tm_email_processed_submit)
            all_submitted_emails_for_uniqueness.add(tm_email_processed_submit)
        
        if len(processed_team_emails_for_db) != 8 and not any("Team Member" in e for e in validation_errors if "mandatory" in e or "invalid" in e or "duplicate" in e or "registered" in e):
             validation_errors.append("Please ensure all 8 unique and valid team member emails are provided, and that they are not already registered users.")

        if validation_errors:
            for err_msg in validation_errors: st.error(f"⚠️ {err_msg}")
        else:
            admin_data_for_db_insert = (
                first_name_submit, last_name_submit, dob_submit_obj.strftime('%Y-%m-%d'), age_submit_val, gender_submit_val,
                city_submit_val if city_submit_val not in ["Select country first", "Select City"] else None,
                country_submit_val if country_submit_val != "Select Country" else None,
                org_level_submit_val, org_name_submit_val,
                final_designation_for_db, 
                final_sports_team_for_db, 
                final_role_for_db,
                email_submit 
            )

            if insert_admin_and_team_members(admin_data_for_db_insert, password_submit, processed_team_emails_for_db):
                st.success(f"✅ Admin registration for '{org_name_submit_val}' (Admin: {email_submit}) successful! Team members will be invited. Redirecting to login...")
                st.balloons()
                admin_full_name_for_email = f"{first_name_submit} {last_name_submit}"
                email_admin_sent = send_admin_registration_email(email_submit, admin_full_name_for_email, org_name_submit_val)
                if not email_admin_sent:
                     st.warning(f"Admin welcome email to {email_submit} could not be sent. Please check logs. You can still log in.")
                
                invitations_failed_count = 0
                if processed_team_emails_for_db:
                    for tm_email_to_invite in processed_team_emails_for_db:
                        if not send_team_member_invitation_email(tm_email_to_invite, admin_full_name_for_email, org_name_submit_val):
                            invitations_failed_count +=1
                if invitations_failed_count > 0:
                    st.warning(f"{invitations_failed_count} team member invitation emails could not be sent. Please check logs or re-invite from dashboard.")
                
                st.session_state.login_success_message = f"Registration for admin {email_submit} ({org_name_submit_val}) successful. Please log in."
                
                keys_to_clear_on_success = [k for k in st.session_state if k.startswith("admin_")]
                for key_admin_success in keys_to_clear_on_success:
                    if key_admin_success in st.session_state: del st.session_state[key_admin_success]
                if "registration_choice" in st.session_state: del st.session_state.registration_choice
                
                main_app_navigate_to_function('login')
                st.rerun()
            else:
                # Error message should have been shown by insert_admin_and_team_members
                pass 

    if st.button("Cancel and Go to Login", key="admin_cancel_and_login_button", use_container_width=True):
        keys_to_clear_on_cancel = [k for k in st.session_state if k.startswith("admin_")]
        for key_admin_cancel_btn in keys_to_clear_on_cancel:
            if key_admin_cancel_btn in st.session_state: del st.session_state[key_admin_cancel_btn]
        if "registration_choice" in st.session_state: del st.session_state.registration_choice
        main_app_navigate_to_function('login')
        st.rerun()

# --- Main Entry Point for User Choice ---
def user_registration_entrypoint(main_app_navigate_to_function):
    set_registration_background(BG_IMAGE_PATH)
    add_registration_logo(LOGO_IMAGE_PATH)
    apply_registration_custom_styles()

    if "registration_choice" not in st.session_state:
        st.session_state.registration_choice = None
    
    if st.session_state.registration_choice is None:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>Choose Your Registration Type</h1>", unsafe_allow_html=True)
        st.markdown("---")
        col_spacer1, col_admin_btn, col_team_btn, col_consultant_btn, col_spacer2 = st.columns([1,2,2,2,1])
        with col_admin_btn:
            if st.button("Sign up as Admin / Organisation Lead", key="choice_admin_signup_button", use_container_width=True):
                st.session_state.registration_choice = "admin"
                st.rerun()
        with col_team_btn:
            if st.button("Sign up as Team Member / Athlete", key="choice_team_signup_button", use_container_width=True):
                st.session_state.registration_choice = "team_member"
                st.rerun()
        with col_consultant_btn:
            if st.button("Sign up as Consultant", key="choice_consultant_signup_button", use_container_width=True):
                st.session_state.registration_choice = "consultant"
                st.rerun()
            
    elif st.session_state.registration_choice == "admin":
        render_admin_registration_view(main_app_navigate_to_function)
    elif st.session_state.registration_choice == "team_member":
        user_registration_2.render_team_member_registration_view(main_app_navigate_to_function)
    elif st.session_state.registration_choice == "consultant":
        try:
            import consultant_registration
            consultant_registration.render_consultant_registration_view(main_app_navigate_to_function)
        except ImportError:
            st.error("Consultant registration feature is currently unavailable (module not found).")
            logging.error("ImportError: consultant_registration.py not found.")
            if st.button("Back to Choices", key="consultant_module_notfound_back_btn"):
                st.session_state.registration_choice = None; st.rerun()
        except AttributeError:
            st.error("Consultant registration feature is currently unavailable (module misconfigured).")
            logging.error("AttributeError: consultant_registration module missing render_consultant_registration_view.")
            if st.button("Back to Choices", key="consultant_module_misconfig_back_btn"):
                st.session_state.registration_choice = None; st.rerun()

def mock_main_app_navigate(page_name):
    st.toast(f"Mock Navigate: Attempting to go to '{page_name}' page.")
    logging.info(f"Mock navigation called for page: {page_name}")
    if page_name == 'login':
        login_msg = st.session_state.pop('login_success_message', "Login page would be displayed here (mocked).")
        st.sidebar.success(f"Navigated to Login (Mock). Message: {login_msg}")
        
        reg_keys_to_clear = [k for k in st.session_state if k.startswith("admin_") or k.startswith("tm_") or k.startswith("c_") or "registration_choice" in k or "login_success_message" in k]
        for key_to_clear_mock in reg_keys_to_clear:
            if key_to_clear_mock in st.session_state:
                del st.session_state[key_to_clear_mock]
        
        # To effectively show a "new page" in mock, we can clear the main area
        # For a real app, st.experimental_rerun() or st.rerun() would be part of navigation logic
        # or Streamlit's multipage app feature would handle it.
        # Here, we'll just display a message.
        st.empty() # Clear previous content
        st.markdown("### Mock Login Page Area")
        st.info(login_msg)
        if st.button("Restart Registration Process (from Mock Login)", key="mock_login_restart_registration"):
            st.session_state.registration_choice = None
            st.rerun()
            
    elif page_name == 'Team_Member_Registration':
        st.session_state.registration_choice = "team_member"
        st.rerun()
    elif page_name == 'Consultant_Registration':
        st.session_state.registration_choice = "consultant"
        st.rerun()
    else:
        st.warning(f"Mock Navigate: Unknown page '{page_name}'. Staying on current view.")

if __name__ == "__main__":
    try:
        st.set_page_config(layout="wide", page_title="VClarifi Registration System")
    except st.errors.StreamlitAPIException as e:
        if "st.set_page_config() has already been called" not in str(e):
            raise 
        # else: pass, already called, common in Streamlit's interactive development

    if '_stcore_dg_messages' not in st.session_state: 
        st.session_state._stcore_dg_messages = []

    st.sidebar.info("Standalone run: Main Registration Module. Navigation is mocked.")
    st.sidebar.markdown(f"""
    **Testing Information:**
    - **DB Host:** `{DB_HOST}`
    - **DB Name:** `{DB_DATABASE}`
    - Ensure image paths are correct for your local system.
    - Ensure email credentials (SENDER_EMAIL, SENDER_APP_PASSWORD) are valid for testing.
    """)
    
    mock_files_content = {
        "user_registration_2.py": """
import streamlit as st
def render_team_member_registration_view(nav_func):
    st.subheader('Team Member Registration (Mocked View from user_registration_2.py)')
    st.write("This is where the team member/athlete registration form would be.")
    if st.button('Go Back to Registration Choices (from Team Mock)', key='mock_team_back_to_choice_btn'):
        st.session_state.registration_choice = None
        st.rerun()
    if st.button("Go to Mock Login (from Team Mock)", key="mock_team_to_login_btn"):
        nav_func("login")
""",
        "consultant_registration.py": """
import streamlit as st
def render_consultant_registration_view(nav_func):
    st.subheader('Consultant Registration (Mocked View from consultant_registration.py)')
    st.write("This is where the consultant registration form would be.")
    if st.button('Go Back to Registration Choices (from Consultant Mock)', key='mock_consultant_back_to_choice_btn'):
        st.session_state.registration_choice = None
        st.rerun()
    if st.button("Go to Mock Login (from Consultant Mock)", key="mock_consultant_to_login_btn"):
        nav_func("login")
"""
    }
    for filename, content in mock_files_content.items():
        if not os.path.exists(filename):
            try:
                with open(filename, "w") as f: f.write(content)
                logging.info(f"Created mock file: {filename}")
            except Exception as e_file:
                logging.error(f"Could not create mock file {filename}: {e_file}")
                st.sidebar.error(f"Could not create mock file {filename}")
                
    user_registration_entrypoint(mock_main_app_navigate)
