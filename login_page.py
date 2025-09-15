import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import boto3
import json
import os

# ---------- FILE PATHS ----------
bg_path = "images/background.jpg"  # Ensure this path is correct
logo_path = "images/VTARA.png"      # Ensure this path is correct

# --- AWS SECRETS MANAGER HELPER FUNCTION ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    """Fetches application secrets from AWS Secrets Manager and caches them."""
    secret_name = "production/vclarifi/secrets"
    region_name = os.environ.get("AWS_REGION", "us-east-1")

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        return json.loads(secret_string)
    except Exception as e:
        st.error(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        return None

# --- REFINED DATABASE CONNECTION CLASS WITH POOLING ---
class DatabaseConnection:
    _pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the database connection pool."""
        if cls._pool is None:
            # Assumes get_aws_secrets() function exists and returns secrets
            secrets = get_aws_secrets()
            if not secrets:
                st.error("Could not load secrets from AWS. Database connection pool failed.")
                return
            
            # Access secrets safely using nested get()
            db_secrets = secrets.get("database", {})
            
            try:
                # The port value must be an integer. We get it, and if it's not present or
                # an invalid type, we default to the standard MySQL port 3306.
                db_port = db_secrets.get("DB_PORT")
                if db_port is not None:
                    db_port = int(db_port)
                else:
                    db_port = 3306
                
                cls._pool = pooling.MySQLConnectionPool(
                    pool_name="vclarifi_pool",
                    pool_size=5,
                    host=db_secrets.get("DB_HOST"),
                    user=db_secrets.get("DB_USER"),
                    password=db_secrets.get("DB_PASSWORD"),
                    port=db_port,
                    database=db_secrets.get("DB_DATABASE")
                )
                
            except mysql.connector.Error as err:
                st.error(f"Database connection pool error: {err}")
                cls._pool = None
            except (TypeError, ValueError) as err:
                st.error(f"Configuration Error: Invalid port number. Check your secret's DB_PORT value. Error: {err}")
                cls._pool = None

    @classmethod
    def get_connection(cls):
        """Gets a connection from the pool."""
        if cls._pool is None:
            cls.initialize_pool()
        
        if cls._pool:
            try:
                # The get_connection() method returns an active connection
                return cls._pool.get_connection()
            except mysql.connector.Error as err:
                st.error(f"Error getting connection from pool: {err}")
                return None
        return None

# ---------- UI STYLING ----------
def set_background(image_path):
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpg;base64,{encoded}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                color: white;
            }}
            [data-testid="stHeader"] {{
                background: rgba(0, 0, 0, 0);
            }}
            .branding img {{
                width: 80px;
            }}
            .stButton>button {{
                width: 100%;
                padding: 15px;
                font-size: 18px;
                border-radius: 8px;
                background-color: #2c662d;
                color: white;
            }}
            .category-container.completed {{
                background-color: #007BFF20 !important;
                border: 2px solid #007BFF;
                border-radius: 10px;
                padding: 10px;
                margin-bottom: 10px;
            }}
            </style>
        """, unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Background image not found at {image_path}")

def apply_styles():
    st.markdown("""
        <style>
        .left-info {{
            color: white;
            font-size: 14px;
            margin-top: 20px;
            padding-left: 60px;
            line-height: 1.6;
        }}
        .inline-info {{
            display: flex;
            gap: 20px;
        }}
        .login-container {{
            background-color: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            width: 400px;
            margin-top: 80px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
        }}
        </style>
    """, unsafe_allow_html=True)

# ---------- REFINED LOGIN FUNCTION ----------
def login(navigate_to):
    # This page config should be in the main app.py, not here,
    # to avoid warnings when switching pages.
    # st.set_page_config(layout="wide")

    # Use session_state to track page changes
    if "page" not in st.session_state:
        st.session_state.page = "Login"

    set_background(bg_path)
    apply_styles()

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        try:
            logo_image = Image.open(logo_path)
            st.image(logo_image, width=300)
            st.markdown("""
            <div class="left-info">
                <div class="inline-info">
                    <div><b>📞 Phone:</b> +123-456-7890</div>
                    <div><b>✉️ E-Mail:</b> hello@vclarifi.com</div>
                </div>
                <div class="inline-info">
                    <div><b>🌐 Website:</b> www.vclarifi.com</div>
                    <div><b>📍 Address:</b> Canberra, Australia</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        except FileNotFoundError:
            st.error(f"Logo image not found at {logo_path}")

    with col_right:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 32px; font-weight: bold; color: navy; text-align: center;">LOGIN TO YOUR ACCOUNT</div>', unsafe_allow_html=True)

        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")

        # Handle login button click
        if st.button("LOGIN"):
            if not email or not password:
                st.error("Both fields are required!")
            elif check_login(email, password):
                st.session_state.user_email = email
                st.session_state.logged_in = True  # Set a state variable for successful login
                st.success("Welcome!")
                st.rerun()  # Rerun the app to navigate to the main page
            else:
                st.error("Invalid email or password.")

        st.markdown("""
            <div style="text-align: center; font-size: 13px; color: #333;">
                Don’t have an account? 
                <a href="#" onclick="window.parent.location.href = '?page=forgot';" style="color: #007BFF; font-weight: bold;">Forgot Password?</a>
            </div>
        """, unsafe_allow_html=True)
        
        # This button also sets a session state variable to trigger navigation.
        if st.button("Click here to Sign Up"):
            st.session_state.page = "User_Registration"
            st.rerun() # Rerun to switch to the registration page

        st.markdown('</div>', unsafe_allow_html=True)
# Example usage for standalone testing
if __name__ == '__main__':
    DatabaseConnection.initialize_pool() # Initialize the pool when the app starts
    
    def dummy_navigate_to(page_name):
        st.success(f"Navigating to {page_name} (dummy)")
        st.stop()

    login(dummy_navigate_to)
