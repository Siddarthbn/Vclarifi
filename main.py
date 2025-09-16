import streamlit as st
import importlib
import boto3
import json
import traceback

# --- AWS SECRETS MANAGER HELPER (CENTRALIZED) ---
@st.cache_data(ttl=600) # Cache secrets for 10 minutes
def get_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.
    This is designed for secrets stored as key-value pairs, which the API
    returns as a single JSON string.
    """
    secret_name = "production/vclarifi/secrets" # Your secret's name
    region_name = "us-east-1"
    
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        print("Secrets Loaded Successfully from AWS.")
        return json.loads(secret_string)
    except Exception as e:
        st.error("FATAL: Could not retrieve secrets from AWS Secrets Manager.")
        st.error(f"Please check the secret name ('{secret_name}') and IAM permissions.")
        st.error(str(e))
        return None

# --- INITIALIZE SESSION STATE ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'

if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# Load secrets ONCE and store them in the session
if 'secrets' not in st.session_state:
    st.session_state.secrets = get_aws_secrets()

def navigate_to(page_name):
    """Changes the current page and reruns the app."""
    st.session_state.current_page = page_name
    st.rerun()

def load_page():
    """Loads and displays the current page based on session state."""
    page_key = st.session_state.current_page
    user_email = st.session_state.get('user_email')
    secrets = st.session_state.get('secrets')

    # Halt immediately if secrets failed to load on startup.
    if not secrets:
        st.warning("Application cannot proceed because configuration failed to load.")
        return

    page_modules = {
        'login': {'module_name': 'login_page', 'function_name': 'login', 'requires_login': False},
        'User_Registration': {'module_name': 'user_registration', 'function_name': 'user_registration_entrypoint', 'requires_login': False},
        'forgot': {'module_name': 'forgot', 'function_name': 'render_forgot_password_page', 'requires_login': False},
        'Survey': {'module_name': 'survey', 'function_name': 'survey', 'requires_login': True},
        # ... your other pages
    }

    page_info = page_modules.get(page_key)
    if not page_info:
        st.error(f"🚫 Page '{page_key}' not found! Defaulting to login.")
        navigate_to('login')
        return

    if page_info['requires_login'] and not user_email:
        st.warning("🔒 You must be logged in to view this page.")
        if st.button("Go to Login"): navigate_to('login')
        return

    try:
        module = importlib.import_module(page_info['module_name'])
        page_function = getattr(module, page_info['function_name'])

        # Pass the secrets dictionary to the page function
        if page_info['requires_login']:
            page_function(navigate_to, user_email, secrets)
        else:
            page_function(navigate_to, secrets)

    except Exception as e:
        st.error(f"🚫 An unexpected error occurred while loading the page '{page_key}':")
        st.code(traceback.format_exc())

if __name__ == "__main__":
    load_page()
