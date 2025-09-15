# user_registration_2.py

import streamlit as st
import mysql.connector
from mysql.connector import Error
import bcrypt  # For hashing passwords
import datetime  # For date of birth
import re  # For email validation
import base64  # For encoding images
import logging # For logging
import smtplib # For sending emails
from email.mime.text import MIMEText # For creating email messages
import boto3

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# --- File Paths (Update these paths to match your environment) ---
# Consider using relative paths or a more robust way to handle assets if deploying
BG_IMAGE_PATH = "C:/Users/DELL/Desktop/background.jpg"
LOGO_IMAGE_PATH = "C:/Users/DELL/Desktop/VTARA.png"


# --- UI Utility Functions ---
def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string for embedding in HTML/CSS."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Warning: Image file not found at {image_path}. Background/logo may not display.")
        logging.warning(f"Image file not found: {image_path}")
        return None
    except Exception as e:
        st.error(f"An error occurred while encoding image {image_path}: {e}")
        logging.error(f"Error encoding image {image_path}: {e}")
        return None

def set_background(image_path):
    """Sets the background image and specific styles for this page."""
    try:
        encoded_bg = encode_image_to_base64(image_path)
        if encoded_bg:
            st.markdown(f"""
                <style>
                    [data-testid="stAppViewContainer"] {{
                        background-image: url("data:image/jpeg;base64,{encoded_bg}");
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        background-attachment: fixed;
                        color: white;
                    }}
                    [data-testid="stHeader"] {{
                        background: rgba(0, 0, 0, 0) !important;
                    }}
                    .stButton>button,
                    div[data-testid="stFormSubmitButton"] button {{
                        background-color: #2c662d !important;
                        color: white !important;
                        padding: 10px 20px;
                        border-radius: 8px;
                        border: none;
                        font-weight: bold;
                        margin: 8px 0px;
                        cursor: pointer;
                        transition: background-color 0.3s ease, transform 0.1s ease;
                        width: auto;
                    }}
                    .stButton>button:hover,
                    div[data-testid="stFormSubmitButton"] button:hover {{
                        background-color: #1e4720 !important; /* Darker shade on hover */
                        transform: scale(1.02);
                    }}
                    .stButton>button:active,
                    div[data-testid="stFormSubmitButton"] button:active {{
                        transform: scale(0.98); /* Slight shrink on click */
                    }}
                    @media screen and (max-width: 768px) {{ /* Responsive header */
                        .custom-header {{
                            flex-direction: column !important;
                            align-items: center !important;
                        }}
                        .custom-header img {{
                            margin-bottom: 10px !important;
                        }}
                    }}
                </style>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error applying page background or styles: {e}")
        logging.error(f"Error applying page background: {e}")

def display_logo_and_text(logo_path):
    """Displays the logo and application title."""
    try:
        encoded_logo = encode_image_to_base64(logo_path)
        if encoded_logo:
            st.markdown(f"""
                <div class="custom-header" style='display: flex; justify-content: space-between; align-items: center; padding: 20px 30px; flex-wrap: wrap; position: relative; z-index: 10;'>
                    <img src="data:image/png;base64,{encoded_logo}" alt="VClarifi Logo" style="width: 70px; margin-right: 15px; height: auto;">
                    <span style='font-family: Arial, sans-serif; font-size: clamp(1.8rem, 2.2vw, 2.5rem); font-weight: bold; color: white; letter-spacing: 1px;'>VCLARIFI</span>
                </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying logo: {e}")
        logging.error(f"Error displaying logo: {e}")

# --- Constants ---
PREDEFINED_COUNTRIES = ["Select Country", "India", "Australia"] # Add more as needed
COUNTRY_CITIES_MAP = {
    "India": ["Select City", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"],
    "Australia": ["Select City", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
}
GENERIC_CITY_LIST = ["Select City"] # Fallback city list

# --- Database Utility Functions ---
def get_db_connection():
    """Establishes and returns a MySQL database connection."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST, database=DB_DATABASE, user=DB_USER, password=DB_PASSWORD
        )
        return connection
    except Error as e:
        st.error(f"Database connection error: {e}. Please check config and DB status.")
        logging.error(f"Database connection error: {e}")
        return None

def is_valid_email_format(email_str):
    """Validates email format using a regular expression."""
    if not email_str: return False
    # Basic regex for email validation
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email_str.strip()) is not None

def is_email_invited_team_member(email_to_check):
    """Checks if an email is in the admin_team_members table (invited)."""
    connection = get_db_connection()
    if not connection:
        # Error already shown by get_db_connection
        return False, None, None # is_invited, org_name, admin_email
    processed_email = email_to_check.strip().lower()
    cursor = None
    try:
        cursor = connection.cursor()
        query = "SELECT organisation_name, admin_email FROM admin_team_members WHERE LOWER(team_member_email) = %s"
        cursor.execute(query, (processed_email,))
        result = cursor.fetchone()
        if result:
            return True, result[0], result[1]  # is_invited, org_name, admin_email
        else:
            return False, None, None
    except Error as e:
        st.error(f"Database error during invitation verification: {e}")
        logging.error(f"DB error during invitation verification for {processed_email}: {e}")
        return False, None, None
    finally:
        if connection and connection.is_connected():
            if cursor: cursor.close()
            connection.close()

def check_if_email_fully_registered(email_to_check):
    """Checks if an email is already present in the user_registration table."""
    connection = get_db_connection()
    if not connection:
        return None # Error shown by get_db_connection
    processed_email = email_to_check.strip().lower()
    cursor = None
    try:
        cursor = connection.cursor()
        query = "SELECT COUNT(*) FROM user_registration WHERE LOWER(Email_Id) = %s"
        cursor.execute(query, (processed_email,))
        result = cursor.fetchone()
        return result[0] > 0 if result else None # Returns True if registered, False if not, None on DB error
    except Error as e:
        st.error(f"Database error checking full registration status for {email_to_check}: {e}")
        logging.error(f"DB error checking full registration for {processed_email}: {e}")
        return None # Indicate error
    finally:
        if connection and connection.is_connected():
            if cursor: cursor.close()
            connection.close()

def insert_team_member_user(tm_data_tuple, password_str):
    """
    Inserts a new team member into the user_registration table.
    tm_data_tuple should contain 13 elements for the fields from first_name to Email_Id.
    'is_admin' is automatically set to FALSE.
    """
    connection = get_db_connection()
    if not connection:
        return False # Error displayed by get_db_connection

    cursor = None
    try:
        cursor = connection.cursor()
        user_query = """
            INSERT INTO user_registration (
                first_name, last_name, date_of_birth, age, gender, city, country,
                organisation_level, organisation_name, designation, sports_team, roles,
                Email_Id, Password, is_admin
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, 
                FALSE 
            )
        """
        hashed_password_bytes = bcrypt.hashpw(password_str.encode('utf-8'), bcrypt.gensalt())

        if len(tm_data_tuple) != 13:
            st.error(f"Data preparation error: Expected 13 data fields for insertion, got {len(tm_data_tuple)}.")
            logging.error(f"Data prep error for insert_team_member_user: expected 13 fields, got {len(tm_data_tuple)}")
            return False

        data_list = list(tm_data_tuple)
        email_index_in_tuple = 12
        if isinstance(data_list[email_index_in_tuple], str):
            data_list[email_index_in_tuple] = data_list[email_index_in_tuple].strip().lower()
        final_tm_data_tuple = tuple(data_list)

        complete_data_for_query = final_tm_data_tuple + (hashed_password_bytes.decode('utf-8'),)

        cursor.execute(user_query, complete_data_for_query)
        connection.commit()
        logging.info(f"Successfully registered team member: {final_tm_data_tuple[email_index_in_tuple]}")
        return True
    except Error as e:
        st.error(f"Database error during team member registration: {e}")
        logging.error(f"DB error during team member registration: {e}")
        if connection and connection.is_connected():
            try:
                connection.rollback()
                logging.info("Database transaction rolled back.")
            except Error as rb_err:
                st.warning(f"Database rollback failed: {rb_err}")
                logging.error(f"Database rollback failed: {rb_err}")
        return False
    finally:
        if connection and connection.is_connected():
            if cursor: cursor.close()
            connection.close()

# --- Email Sending Function ---
def send_registration_confirmation_email(recipient_email, first_name, organisation_name):
    """Sends a registration confirmation email to the newly registered team member."""
    if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
        logging.critical("Email sending misconfiguration: SENDER_EMAIL or SENDER_APP_PASSWORD is not set.")
        return False

    subject = f"Welcome to VClarifi, {first_name}!"
    body = f"""
Hello {first_name},

Welcome to VClarifi!

Your registration as a team member for '{organisation_name}' is complete. You can now log in to the VClarifi application using your registered email and password.

If you have any questions, please contact your organisation's administrator.

Sincerely,
The VClarifi Team
"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            # server.set_debuglevel(1) # Uncomment for verbose SMTP logs if troubleshooting
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        logging.info(f"Registration confirmation email successfully sent to {recipient_email}.")
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error(f"SMTP Authentication Error for {SENDER_EMAIL}. Check App Password and ensure 'less secure app access' is handled correctly if not using App Passwords.")
    except smtplib.SMTPServerDisconnected:
        logging.error("SMTP Server Disconnected unexpectedly during email sending.")
    except smtplib.SMTPConnectError:
        logging.error(f"Failed to connect to SMTP server {SMTP_SERVER}:{SMTP_PORT}.")
    except ConnectionRefusedError:
        logging.error(f"Connection refused by SMTP server {SMTP_SERVER}:{SMTP_PORT}.")
    except TimeoutError:
        logging.error(f"Connection to SMTP server {SMTP_SERVER}:{SMTP_PORT} timed out.")
    except OSError as e:
        logging.error(f"OS error during email sending: {e}")
    except Exception as e:
        # Use logging.exception to include stack trace for unexpected errors
        logging.exception(f"An unexpected error occurred during email sending to {recipient_email}: {e}")
    return False

# --- Main Rendering Function for Team Member Registration ---
def render_team_member_registration_view(main_app_navigate_to_function):
    """Renders the multi-step team member registration page."""
    set_background(BG_IMAGE_PATH)
    display_logo_and_text(LOGO_IMAGE_PATH)

    st.markdown("<h1 style='text-align: center; color: white; margin-top: 20px; margin-bottom: 30px;'>Team Member / Athlete Registration</h1>", unsafe_allow_html=True)

    # Initialize session state variables for the registration flow if they don't exist
    # These should ideally be initialized once when the app starts or when this page/module is first loaded.
    if "tm_reg_step" not in st.session_state:
        st.session_state.tm_reg_step = "verify_email_step"
    if "tm_verified_email" not in st.session_state:
        st.session_state.tm_verified_email = ""
    if "tm_org_name" not in st.session_state:
        st.session_state.tm_org_name = ""
    # Default Date of Birth to 18 years ago from today (January 1st)
    if "tm_dob_ui" not in st.session_state:
        st.session_state.tm_dob_ui = datetime.date(datetime.date.today().year - 18, 1, 1)
    if "tm_country_ui" not in st.session_state:
        st.session_state.tm_country_ui = PREDEFINED_COUNTRIES[0] # "Select Country"
    if "tm_city_ui" not in st.session_state:
        st.session_state.tm_city_ui = GENERIC_CITY_LIST[0] # "Select City"

    # --- Step 1: Verify Email ---
    if st.session_state.tm_reg_step == "verify_email_step":
        st.subheader("Step 1: Verify Your Invitation Email")
        st.write("Please enter the email address your organisation's admin used to add you to the team.")
        with st.form("tm_email_verification_form"):
            email_input_raw = st.text_input("Your Registered Email Address", key="tm_email_verify_input")
            submit_verify_button = st.form_submit_button("Verify Email")

            if submit_verify_button:
                email_input_stripped = email_input_raw.strip()
                if not email_input_stripped:
                    st.error("Email address cannot be empty.")
                elif not is_valid_email_format(email_input_stripped):
                    st.error("Please enter a valid email address format.")
                else:
                    processed_email_input = email_input_stripped.lower()
                    is_invited, org_name, _ = is_email_invited_team_member(processed_email_input)

                    if is_invited:
                        already_fully_registered = check_if_email_fully_registered(processed_email_input)
                        if already_fully_registered is True:
                            st.warning(f"The email '{email_input_stripped}' is already associated with a fully registered user account. Please log in.")
                        elif already_fully_registered is None:
                            # Error message already shown by check_if_email_fully_registered
                            pass
                        else: # Not fully registered (False), can proceed
                            st.session_state.tm_verified_email = processed_email_input
                            st.session_state.tm_org_name = org_name
                            st.session_state.tm_reg_step = "fill_details_step"
                            st.success(f"Invitation verified for {st.session_state.tm_org_name}! Please complete your profile details below.")
                            st.rerun()
                    else:
                        connection_available = True # Assume connection is available
                        # Check if is_invited is False due to DB error or genuinely not found
                        if org_name is None: # is_email_invited_team_member returns None for org_name on DB error
                            temp_conn = get_db_connection() # This will show its own error if it fails
                            if not temp_conn:
                                connection_available = False
                            elif temp_conn.is_connected(): # Close if successfully opened for check
                                temp_conn.close()

                        if not connection_available:
                            # Error already handled by get_db_connection called within is_email_invited_team_member
                            pass
                        else: # Email genuinely not found in invited list
                            st.error(f"The email '{email_input_stripped}' was not found in our list of invited team members. "
                                     "Please verify the email with your organisation admin or ensure they have added you.")

        if st.button("Cancel and Go to Login", key="tm_v_cancel_and_go_to_login"):
            # Clear all team member registration specific session state
            keys_to_clear = [k for k in st.session_state if k.startswith("tm_")]
            for key_to_clear in keys_to_clear:
                if key_to_clear in st.session_state: del st.session_state[key_to_clear]

            # If your main app uses 'registration_choice' to manage which registration type was selected
            if "registration_choice" in st.session_state:
                del st.session_state.registration_choice

            main_app_navigate_to_function('login') # Navigate to login page
            st.rerun()

    # --- Step 2: Fill Profile Details ---
    elif st.session_state.tm_reg_step == "fill_details_step":
        st.subheader(f"Step 2: Complete Your Profile for '{st.session_state.tm_org_name}'")
        st.markdown(f"You are registering with the email: **{st.session_state.tm_verified_email}**")

        with st.form("team_member_full_registration_form"):
            st.markdown("#### Personal Details")
            col1_pd, col2_pd = st.columns(2)
            col1_pd.text_input("First Name", key="tm_fn_widget", value=st.session_state.get("tm_fn_widget", ""))
            col2_pd.text_input("Last Name", key="tm_ln_widget", value=st.session_state.get("tm_ln_widget", ""))
            col1_pd.text_input("Create Password (min. 8 characters)", type="password", key="tm_pw_widget")
            col2_pd.text_input("Confirm Password", type="password", key="tm_cpw_widget")

            if not isinstance(st.session_state.tm_dob_ui, datetime.date): # Ensure it's a date object
                st.session_state.tm_dob_ui = datetime.date(datetime.date.today().year - 18, 1, 1)
            tm_dob_value_from_widget = col1_pd.date_input("Date of Birth",
                                                            value=st.session_state.tm_dob_ui,
                                                            min_value=datetime.date(1920, 1, 1),
                                                            max_value=datetime.date.today(), # Cannot be born in future
                                                            key="tm_dob_widget_for_form")
            col2_pd.number_input("Age", min_value=5, max_value=120, step=1,
                                   key="tm_age_widget_manual",
                                   value=st.session_state.get("tm_age_widget_manual", 18), # Default to 18 if not set
                                   help="Enter your current age.")

            gender_options = ["Select", "Male", "Female", "Non-binary", "Prefer not to say"]
            st.selectbox("Gender", gender_options,
                         key="tm_gender_widget",
                         index=gender_options.index(st.session_state.get("tm_gender_widget", "Select")))

            st.markdown("#### Location Details (Optional)")
            col1_loc, col2_loc = st.columns(2)

            if st.session_state.tm_country_ui not in PREDEFINED_COUNTRIES: # Ensure valid default
                st.session_state.tm_country_ui = PREDEFINED_COUNTRIES[0]
            current_country_idx = PREDEFINED_COUNTRIES.index(st.session_state.tm_country_ui)
            tm_country_selected_from_widget = col1_loc.selectbox("Country", PREDEFINED_COUNTRIES,
                                                                 index=current_country_idx,
                                                                 key="tm_country_widget_for_form")
            # City selection (dependent on country)
            if tm_country_selected_from_widget != "Select Country":
                cities_for_country = COUNTRY_CITIES_MAP.get(tm_country_selected_from_widget, GENERIC_CITY_LIST[:])
                city_disabled_status = False
                if st.session_state.tm_city_ui not in cities_for_country: # Reset city if not in new list
                    st.session_state.tm_city_ui = cities_for_country[0]
            else:
                cities_for_country = ["Select country first"] # Placeholder if no country
                city_disabled_status = True
                st.session_state.tm_city_ui = cities_for_country[0] # Default to the placeholder

            current_city_idx_for_selectbox = 0 # Default to first item
            if st.session_state.tm_city_ui in cities_for_country:
                try:
                    current_city_idx_for_selectbox = cities_for_country.index(st.session_state.tm_city_ui)
                except ValueError: # Should not happen if logic above is correct
                    current_city_idx_for_selectbox = 0

            tm_city_selected_from_widget = col2_loc.selectbox("City", cities_for_country,
                                                              index=current_city_idx_for_selectbox,
                                                              disabled=city_disabled_status,
                                                              key="tm_city_widget_for_form")

            st.markdown(f"#### Your Role at '{st.session_state.tm_org_name}'")
            st.text_input("Your Specific Team (e.g., U19 Cricket, Senior Football)",
                          key="tm_specific_team_widget",
                          value=st.session_state.get("tm_specific_team_widget", ""))
            st.text_input("Your Primary Role (e.g., Player, Analyst, Coach)",
                          key="tm_role_widget",
                          value=st.session_state.get("tm_role_widget", ""))
            team_member_org_level = "Team Member / Athlete" # Fixed for this registration type

            st.markdown("---") # Visual separator
            submit_tm_details_button = st.form_submit_button("Register My Profile")

        # --- Dynamic UI Update Logic (Rerun if dependent inputs change to update dependent selects) ---
        rerun_needed = False
        if tm_dob_value_from_widget != st.session_state.tm_dob_ui:
            st.session_state.tm_dob_ui = tm_dob_value_from_widget
            rerun_needed = True # Could update age based on DOB here if desired
        if tm_country_selected_from_widget != st.session_state.tm_country_ui:
            st.session_state.tm_country_ui = tm_country_selected_from_widget
            # Reset city when country changes, to the default "Select City" or first valid city
            st.session_state.tm_city_ui = COUNTRY_CITIES_MAP.get(tm_country_selected_from_widget, GENERIC_CITY_LIST[:])[0]
            rerun_needed = True
        # Only update city from widget if it's enabled and different
        if not city_disabled_status and tm_city_selected_from_widget != st.session_state.tm_city_ui:
            st.session_state.tm_city_ui = tm_city_selected_from_widget
            # No rerun needed just for city change, as it doesn't affect other fields dynamically in this setup
            # However, if it did, set rerun_needed = True

        if rerun_needed:
            st.rerun()

        # --- Form Submission Processing ---
        if submit_tm_details_button:
            s = st.session_state # Alias for convenience
            errors = []

            # Validation (using s.get() which reads directly from session_state)
            if not s.get("tm_fn_widget","").strip(): errors.append("First Name is required.")
            if not s.get("tm_ln_widget","").strip(): errors.append("Last Name is required.")
            if not s.get("tm_pw_widget","") or len(s.get("tm_pw_widget","")) < 8: errors.append("Password must be at least 8 characters.")
            if s.get("tm_pw_widget","") != s.get("tm_cpw_widget",""): errors.append("Passwords do not match.")
            if s.get("tm_age_widget_manual", 0) < 5 : errors.append("Please enter a valid age.")
            if s.get("tm_gender_widget","Select") == "Select": errors.append("Gender is required.")
            # Add more specific validations if needed (e.g., for role, team)

            if errors:
                for e_msg in errors: st.error(f"Validation Error: {e_msg}")
            else:
                # Prepare data for database insertion
                data_for_insert = (
                    s.tm_fn_widget.strip(),
                    s.tm_ln_widget.strip(),
                    s.tm_dob_widget_for_form.strftime('%Y-%m-%d'), # DOB from widget
                    s.tm_age_widget_manual,
                    s.tm_gender_widget,
                    s.tm_city_widget_for_form if s.tm_city_widget_for_form not in ["Select country first", GENERIC_CITY_LIST[0]] else None,
                    s.tm_country_widget_for_form if s.tm_country_widget_for_form != PREDEFINED_COUNTRIES[0] else None,
                    team_member_org_level,
                    s.tm_org_name,
                    None, # Designation field - assuming None for team members registered this way
                    s.tm_specific_team_widget.strip() if s.get("tm_specific_team_widget","").strip() else None,
                    s.tm_role_widget.strip() if s.get("tm_role_widget","").strip() else None,
                    s.tm_verified_email
                )

                if insert_team_member_user(data_for_insert, s.tm_pw_widget):
                    st.success(f"Welcome, {s.tm_fn_widget.strip()}! Your registration for {s.tm_org_name} is complete.")
                    # st.balloons() # Removed as per request

                    # Send confirmation email
                    email_sent = send_registration_confirmation_email(
                        recipient_email=s.tm_verified_email,
                        first_name=s.tm_fn_widget.strip(),
                        organisation_name=s.tm_org_name
                    )
                    if not email_sent:
                        # Logged in the function, no extra UI message needed here to keep it clean
                        logging.warning(f"Registration for {s.tm_verified_email} was successful, but confirmation email FAILED to send. This was not shown to the user.")

                    st.session_state.login_success_message = f"Team member {s.tm_verified_email} registered. Please log in."

                    # Clear all team member registration specific session state
                    keys_to_clear_on_success = [k for k in st.session_state if k.startswith("tm_")]
                    for key_s in keys_to_clear_on_success:
                        if key_s in st.session_state: del st.session_state[key_s]
                    if "registration_choice" in st.session_state: # If part of a larger flow
                        del st.session_state.registration_choice

                    main_app_navigate_to_function('login')
                    st.rerun()
                else:
                    # Error message is already displayed by insert_team_member_user
                    pass

        if st.button("Cancel and Verify Different Email", key="tm_f_cancel_and_reverify_email"):
            st.session_state.tm_reg_step = "verify_email_step"
            # Clear all tm_ specific state except tm_reg_step itself
            keys_to_clear_for_reverify = [k for k in st.session_state if k.startswith("tm_") and k != "tm_reg_step"]
            for key_r in keys_to_clear_for_reverify:
                if key_r in st.session_state: del st.session_state[key_r]

            # Explicitly reset UI control values to their initial defaults for a clean Step 1 appearance
            st.session_state.tm_verified_email = ""
            st.session_state.tm_org_name = ""
            st.session_state.tm_dob_ui = datetime.date(datetime.date.today().year - 18, 1, 1)
            st.session_state.tm_country_ui = PREDEFINED_COUNTRIES[0]
            st.session_state.tm_city_ui = GENERIC_CITY_LIST[0]
            # Also clear any direct widget values that might have been stored from the form
            for widget_key in ["tm_fn_widget", "tm_ln_widget", "tm_pw_widget", "tm_cpw_widget",
                               "tm_age_widget_manual", "tm_gender_widget",
                               "tm_specific_team_widget", "tm_role_widget"]:
                if widget_key in st.session_state:
                    del st.session_state[widget_key]
            st.rerun()


# Example of how to call this if it's part of a larger app
if __name__ == "__main__":
    # Dummy navigator function for standalone testing
    def dummy_main_app_navigator(page_name):
        st.info(f"If this were the main app, it would navigate to: '{page_name}'")
        if page_name == 'login' and hasattr(st.session_state, 'login_success_message'):
            st.info(f"Message for login page: {st.session_state.login_success_message}")

    # Initialize session state for steps and UI controls if not present (for standalone testing)
    # This ensures that st.session_state.get(key, default_value) in widget definitions
    # has a defined state key to get from, even on the very first run of the script.
    default_tm_states = {
        "tm_reg_step": "verify_email_step",
        "tm_verified_email": "",
        "tm_org_name": "",
        "tm_dob_ui": datetime.date(datetime.date.today().year - 18, 1, 1),
        "tm_country_ui": PREDEFINED_COUNTRIES[0],
        "tm_city_ui": GENERIC_CITY_LIST[0],
        "tm_fn_widget": "",
        "tm_ln_widget": "",
        "tm_age_widget_manual": 18,
        "tm_gender_widget": "Select",
        "tm_specific_team_widget": "",
        "tm_role_widget": ""
        # Add tm_pw_widget, tm_cpw_widget if you want to pre-fill them (usually not for passwords)
    }
    for key, value in default_tm_states.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    render_team_member_registration_view(dummy_main_app_navigator)
