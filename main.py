import streamlit as st
import importlib
import boto3
import json
import traceback

# ==============================================================================
# --- AWS SECRETS MANAGER HELPER ---
# ==============================================================================

@st.cache_data(ttl=600)  # Cache secrets for 10 minutes to reduce API calls
def get_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.

    This function is designed for secrets stored as key-value pairs, which the AWS API
    returns as a single JSON string. It includes robust error handling.
    """
    secret_name = "production/vclarifi/secrets"  # Your secret's unique name/path
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        print("Secrets Loaded Successfully from AWS.")
        return json.loads(secret_string)
    except Exception as e:
        # Log the full error for debugging but show a user-friendly message
        logging.error(f"AWS Secrets Manager Error: {e}")
        st.error("FATAL: Could not retrieve application secrets from AWS.")
        st.error("Please contact support and check IAM permissions and secret name.")
        return None

# ==============================================================================
# --- SESSION STATE INITIALIZATION ---
# ==============================================================================

# Initialize core session state keys if they don't exist.
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'

if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# Load secrets ONCE per session and store them.
if 'secrets' not in st.session_state:
    st.session_state.secrets = get_aws_secrets()

# ==============================================================================
# --- NAVIGATION AND PAGE ROUTING ---
# ==============================================================================

def navigate_to(page_name):
    """
    Sets the current page in the session state and triggers a rerun.
    This is the central function for navigating between pages.

    Args:
        page_name (str): The key of the page to navigate to (from page_modules).
    """
    st.session_state.current_page = page_name
    st.rerun()

def load_page():
    """
    Acts as the main router for the application.

    It reads the current page from session state, checks for authentication,
    and dynamically imports and calls the appropriate function from other files.
    """
    page_key = st.session_state.current_page
    secrets = st.session_state.get('secrets')

    # Halt the entire application if secrets failed to load on startup.
    if not secrets:
        st.warning("Application cannot proceed because its configuration failed to load.")
        return

    # --- Page Module Configuration ---
    # This dictionary is the central routing table for the app.
    #   'module_name': The .py file to import (without the .py extension).
    #   'function_name': The function to call within that file.
    #   'requires_login': A boolean to protect pages that need an authenticated user.
    page_modules = {
        'login': {'module_name': 'login_page', 'function_name': 'login', 'requires_login': False},
        'User_Registration': {'module_name': 'user_registration', 'function_name': 'user_registration_entrypoint', 'requires_login': False},
        'forgot': {'module_name': 'forgot', 'function_name': 'render_forgot_password_page', 'requires_login': False},
        'Survey': {'module_name': 'survey', 'function_name': 'render_survey_page', 'requires_login': True},
        # Add other pages here, e.g.:
        # 'Dashboard': {'module_name': 'dashboard', 'function_name': 'render_dashboard', 'requires_login': True},
    }

    page_info = page_modules.get(page_key)

    if not page_info:
        st.error(f"🚫 Page '{page_key}' not found! Defaulting to login page.")
        navigate_to('login')
        return

    # --- Authentication Check ---
    user_email = st.session_state.get('user_email')
    if page_info['requires_login'] and not user_email:
        st.warning("🔒 You must be logged in to view this page.")
        if st.button("Go to Login"):
            navigate_to('login')
        return

    # --- Dynamic Page Loading and Execution ---
    try:
        module = importlib.import_module(page_info['module_name'])
        page_function = getattr(module, page_info['function_name'])

        # Prepare arguments to pass to the page function for flexibility.
        # This allows page functions to have different signatures.
        args_to_pass = {
            "navigate_to": navigate_to,
            "user_email": user_email,
            "secrets": secrets
        }
        
        # Call the target function with the prepared arguments.
        page_function(**args_to_pass)

    except Exception as e:
        st.error(f"🚫 An unexpected error occurred while loading the '{page_key}' page.")
        # Use an expander for the traceback to keep the UI clean.
        with st.expander("Click to see error details"):
            st.code(traceback.format_exc())

# ==============================================================================
# --- APPLICATION ENTRY POINT ---
# ==============================================================================
if __name__ == "__main__":
    load_page()
