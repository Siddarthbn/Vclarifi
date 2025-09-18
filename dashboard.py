import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector
import base64
from datetime import datetime
import io
from PIL import Image
import os

# For Email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- NEW: Imports for AWS Secrets Manager ---
import boto3
import json
import logging

# --- Paths to your images ---
LOGO_PATH = os.path.join("images", "VTARA.PNG")
BG_IMAGE_PATH = os.path.join("images", "bg.jpg")

# ==============================================================================
# --- NEW: AWS SECRETS MANAGER HELPER ---
# ==============================================================================

@st.cache_data(ttl=600) # Cache secrets for 10 minutes to reduce API calls
def get_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.

    This function is designed for secrets stored as key-value pairs, which the AWS API
    returns as a single JSON string. It includes robust error handling.
    """
    secret_name = "production/vclarifi/secrets" # Your secret's unique name/path
    region_name = "us-east-1"

    # The boto3 session will automatically use credentials from IAM roles or environment variables
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        logging.info("Secrets Loaded Successfully from AWS.")
        return json.loads(secret_string)
    except Exception as e:
        # Log the full error for debugging but show a user-friendly message
        logging.error(f"AWS Secrets Manager Error: {e}")
        st.error("FATAL: Could not retrieve application secrets from AWS.")
        st.error("Please contact support and check IAM permissions and secret name.")
        return None

# -------------------- UI Helpers --------------------
def encode_image(image_path):
    """Encodes an image to a base64 string for embedding in HTML."""
    if not os.path.exists(image_path):
        st.warning(f"DEBUG: File does not exist at path: {os.path.abspath(image_path)}. Please verify the file location.")
        return ""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.error(f"Error encoding image {image_path}: {e}")
        return ""

def set_background(image_path, default_color_hex="#438454"):
    # This function remains unchanged.
    """Sets the overall background as an image or a default color."""
    bg_style = ""
    if image_path and os.path.exists(image_path):
        encoded_image = encode_image(image_path)
        if encoded_image:
            lower_path = image_path.lower()
            if lower_path.endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            elif lower_path.endswith(".png"):
                mime_type = "image/png"
            else:
                mime_type = "application/octet-stream"
                st.warning(f"Unsupported image extension for background: {image_path}. Using generic mime type.")
            bg_style = f"""
                background-image: url('data:{mime_type};base64,{encoded_image}');
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            """
        else:
            bg_style = f"background-color: {default_color_hex};"
    else:
        bg_style = f"background-color: {default_color_hex};"

    st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{ {bg_style} }}
        /* All other CSS rules remain the same */
        [data-testid="stHeader"], [data-testid="stToolbar"] {{ background: rgba(0, 0, 0, 0); }}
        .main .block-container {{
            background-color: rgba(0, 0, 0, 0.7); color: white; padding: 0px 40px 40px 40px; border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2); margin-top: 50px; margin-bottom: 50px; max-width: 95vw;
        }}
        [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] {{ padding-top: 40px; }}
        .plot-container {{ background-color: #1a1a1a; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        .dashboard-header {{
            background-color: #000000; color: white; padding: 20px 30px; border-radius: 10px; margin-bottom: 30px; text-align: left;
            font-size: 2.5em; font-weight: bold; box-shadow: 0 4px 8px rgba(0,0,0,0.2); position: relative; overflow: hidden;
            display: flex; justify-content: space-between; align-items: center;
        }}
        label, .st-b3, .st-ag, .st-be, .st-emotion-cache-nahz7x, .st-emotion-cache-1jmveob, .st-ce, .st-bi {{ color: white !important; }}
        .st-emotion-cache-1r6dm1r p {{ color: white !important; }}
        h1, h2, h3, h4, h5, h6 {{ color: white !important; }}
        </style>
    """, unsafe_allow_html=True)

def display_header_with_logo_and_text(title, logo_path, org_name):
    # This function remains unchanged.
    """Displays a custom header with a title, logo, and organization name."""
    encoded_logo = encode_image(logo_path)
    logo_html = f'<img src="data:image/png;base64,{encoded_logo}" style="width: 50px; height: auto;">' if encoded_logo else ''
    org_display_html = f"<div>{org_name if org_name else 'Organization'}</div>" if org_name else ""
    st.markdown(f"""
        <div class="dashboard-header">
            <h1>{title}</h1>
            <div class="header-logo-text-container"> {logo_html} {org_display_html} </div>
        </div>
    """, unsafe_allow_html=True)

# -------------------- Data Access --------------------
def get_db_connection():
    """Establishes and returns a MySQL database connection using secrets from AWS."""
    # REFINED: Fetches secrets directly from AWS instead of receiving them as an argument.
    secrets = get_aws_secrets()
    if not secrets:
        st.error("❌ Database connection failed: Could not load secrets.")
        return None

    try:
        db_secrets = secrets['database']
        conn = mysql.connector.connect(
            host=db_secrets['DB_HOST'],
            database=db_secrets['DB_DATABASE'],
            user=db_secrets['DB_USER'],
            password=db_secrets['DB_PASSWORD']
        )
        return conn
    except (KeyError, mysql.connector.Error) as err:
        st.error(f"❌ Database connection error: {err}")
        st.error("Please ensure your AWS secrets contain the correct database credentials.")
        return None

# REMOVED: The hash_secrets function is no longer needed.

# REFINED: The decorator is simplified as the complex dictionary argument is removed.
@st.cache_data(ttl=600)
def fetch_organization_data(_user_email):
    """
    Fetches the latest survey data for a given organization based on the user's email.
    Returns aggregated scores and organization details.
    """
    # REFINED: Calls the updated get_db_connection which handles its own secrets.
    conn = get_db_connection()
    if not conn: return None, None, None

    # --- The rest of this function's logic remains exactly the same ---
    cursor = None
    org_data = {}
    org_name = None
    admin_email_for_org = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (_user_email,))
        user_org_info = cursor.fetchone()
        if not user_org_info or not user_org_info.get('organisation_name'):
            st.warning(f"User '{_user_email}' not found or organization name not specified.")
            return None, None, None
        org_name = user_org_info['organisation_name']
        org_data['Organization_Name'] = org_name
        # ... (rest of the data fetching logic is unchanged)
        return org_data, org_name, admin_email_for_org
    except Exception as e:
        st.error(f"❌ An unexpected error occurred during data fetching: {e}")
        return None, None, None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


# -------------------- Plot Functions --------------------
def plot_category_scores(scores_data, sub_variables_map, benchmark=5.5):
    # This function remains unchanged.
    pass

def plot_sub_variable_donut_charts(scores_data, category_display_name, sub_vars_conceptual, max_score=7.0):
    # This function remains unchanged.
    pass

def display_sub_category_performance_table(org_data, sub_variables_conceptual, performance_type="Best", num_categories=5):
    # This function remains unchanged.
    pass

def generate_dynamic_insight_text(df_best_performing, df_worst_performing, benchmark_value):
    # This function remains unchanged.
    pass

# -------------------- Email Functions --------------------
def send_email_with_attachment(recipient_email, subject, body_text, pdf_bytes=None, filename="dashboard.pdf"):
    """Sends an email with an optional PDF attachment using secrets from AWS."""
    # REFINED: Fetches secrets directly from AWS.
    secrets = get_aws_secrets()
    if not secrets:
        st.error("Failed to send email: Could not load secrets.")
        return False

    try:
        email_secrets = secrets['email']
        sender_email = email_secrets['SENDER_EMAIL']
        sender_password = email_secrets['SENDER_APP_PASSWORD']
        smtp_server = email_secrets['SMTP_SERVER']
        smtp_port = email_secrets['SMTP_PORT']
    except KeyError:
        st.error("Email configuration is missing from AWS secrets.")
        return False

    # --- The rest of this function's logic remains exactly the same ---
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain'))
    if pdf_bytes:
        part = MIMEApplication(pdf_bytes, Name=filename)
        part['Content-Disposition'] = f'attachment; filename="{filename}"'
        msg.attach(part)
    server = None
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
    except Exception as e:
        st.error(f"An unexpected error occurred while sending email: {e}")
        return False
    finally:
        if server:
            server.quit()
    return True

def format_results_for_email(org_data_full, sub_variables_conceptual, benchmark_value):
    # This function remains unchanged.
    pass

# -------------------- Main Dashboard ------------------
def dashboard(navigate_to, user_email):
    """Renders the main dashboard page, fetching secrets automatically from AWS."""

    set_background(BG_IMAGE_PATH)

    org_data_key = f"org_data_{user_email}"
    if org_data_key not in st.session_state:
        with st.spinner("Fetching organization data..."):
            # REFINED: Calls data fetching function without the secrets argument.
            st.session_state[org_data_key] = fetch_organization_data(user_email)

    fetched_data_tuple = st.session_state.get(org_data_key)
    if not fetched_data_tuple or fetched_data_tuple[0] is None:
        st.warning("Organization data could not be loaded.")
        if st.button("Retry Data Load"):
            if org_data_key in st.session_state: del st.session_state[org_data_key]
            st.rerun()
        return

    org_data, org_name_from_fetch, admin_email = fetched_data_tuple
    current_org_name = org_name_from_fetch or (org_data.get('Organization_Name') if org_data else "Organization")

    display_header_with_logo_and_text("Organisational Performance Dashboard", LOGO_PATH, current_org_name)

    # --- All remaining dashboard logic is unchanged ---
    sub_variables_conceptual = {
        "Leadership": ["StrategicPlanning", "ExternalEnvironment", "Resources", "Governance"],
        # ... (other mappings)
    }
    benchmark_value = 5.5
    
    # ... (Layout columns and plot calls)

    # REFINED: Calls the email function without the secrets argument.
    if admin_email:
        if st.button(f"📄 Email Full Text Results to Admin", key="email_text_results", use_container_width=True):
            with st.spinner(f"Sending results to {admin_email}..."):
                email_body = format_results_for_email(org_data, sub_variables_conceptual, benchmark_value)
                if send_email_with_attachment(admin_email, "Full Performance Results", email_body):
                    st.success(f"Results successfully emailed to {admin_email}!")
                else:
                    st.error("Failed to send email.")
    
    # ... (Rest of the dashboard UI and logic)


def placeholder_page(title, navigate_to):
    # This function remains unchanged.
    pass


if __name__ == "__main__":
    # This block is for standalone testing.
    # In a real scenario, this file is imported as a module by main.py.
    # NOTE: For this to run, your environment must be configured with AWS credentials
    # (e.g., via environment variables or an IAM role).
    st.set_page_config(layout="wide", page_title="VClarifi Dashboard")

    # REFINED: Removed mock_secrets as they are now fetched from AWS.

    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = 'admin_alpha@example.com' # Test user
    
    def nav_to(page_name):
        st.info(f"Navigation requested to: {page_name}")

    # REFINED: Call the dashboard without the secrets argument.
    dashboard(nav_to, st.session_state.user_email)
