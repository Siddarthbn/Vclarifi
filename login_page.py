import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import boto3
import json
import logging

# ---------- FILE PATHS ----------
BG_PATH = "images/background.jpg"  # Ensure this path is correct
LOGO_PATH = "images/vtara.png"     # Ensure this path is correct

# Setup logger
logger = logging.getLogger(__name__)

# --- AWS SECRETS MANAGER HELPER FUNCTION ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    """Fetches application secrets from AWS Secrets Manager and caches them."""
    secret_name = "production/vclarifi/app_secrets"
    region_name = "us-east-1"  # Change to your AWS region if different

    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region_name)
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response["SecretString"]
        return json.loads(secret_string)
    except Exception as e:
        logger.error(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        return None

# --- DATABASE CONNECTION CLASS WITH POOLING ---
class DatabaseConnection:
    _pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the database connection pool."""
        if cls._pool is not None:
            return

        secrets = get_aws_secrets()
        if not secrets:
            logger.error("Could not load secrets from AWS. Database connection pool failed.")
            return

        try:
            cls._pool = pooling.MySQLConnectionPool(
                pool_name="vclarifi_pool",
                pool_size=5,
                host=secrets.get("DB_HOST"),
                user=secrets.get("DB_USER"),
                password=secrets.get("DB_PASSWORD"),
                database=secrets.get("DB_DATABASE"),
            )
            logger.info("Database connection pool initialized successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Database connection pool error: {err}")
            cls._pool = None

    @classmethod
    def get_connection(cls):
        """Gets a connection from the pool or initializes the pool if needed."""
        if cls._pool is None:
            cls.initialize_pool()

        if cls._pool:
            try:
                return cls._pool.get_connection()
            except mysql.connector.Error as e:
                logger.error(f"Error getting connection from pool: {e}")
                return None
        return None

# --- LOGIN CHECK FUNCTION ---
def check_login(email: str, password: str) -> bool:
    """Checks user credentials against the database using a connection from the pool."""
    conn = None
    cursor = None

    try:
        conn = DatabaseConnection.get_connection()
        if conn is None:
            logger.warning("Failed to get DB connection from pool.")
            return False

        cursor = conn.cursor()
        cursor.execute("SELECT Password FROM user_registration WHERE Email_Id = %s", (email,))
        result = cursor.fetchone()

        if result and result[0]:
            stored_hashed_password = result[0]
            if isinstance(stored_hashed_password, str):
                stored_hashed_password = stored_hashed_password.encode("utf-8")

            if bcrypt.checkpw(password.encode("utf-8"), stored_hashed_password):
                return True
        return False

    except mysql.connector.Error as err:
        logger.error(f"Database query error during login: {err}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()  # Return connection to pool

# ---------- UI STYLING ----------
def set_background(image_path: str):
    """Sets the background image for the app."""
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True,
        )
    except FileNotFoundError:
        st.error(f"Background image not found at {image_path}")

def apply_styles():
    """Applies custom CSS styles."""
    st.markdown(
        """
        <style>
        .left-info {
            color: white;
            font-size: 14px;
            margin-top: 20px;
            padding-left: 60px;
            line-height: 1.6;
        }
        .inline-info {
            display: flex;
            gap: 20px;
        }
        .login-container {
            background-color: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            width: 400px;
            margin-top: 80px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------- LOGIN FUNCTION ----------
def login(navigate_to):
    """Renders the login page."""
    st.set_page_config(layout="wide")

    # Handle special query params for navigation
    page = st.experimental_get_query_params().get("page", [None])[0]
    if page == "forgot":
        st.experimental_set_query_params()
        navigate_to("forgot")
        return

    set_background(BG_PATH)
    apply_styles()

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        try:
            logo_image = Image.open(LOGO_PATH)
            st.image(logo_image, width=300)
            st.markdown(
                """
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
                """,
                unsafe_allow_html=True,
            )
        except FileNotFoundError:
            st.error(f"Logo image not found at {LOGO_PATH}")

    with col_right:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size: 32px; font-weight: bold; color: navy; text-align: center;">LOGIN TO YOUR ACCOUNT</div>',
            unsafe_allow_html=True,
        )

        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")

        if st.button("LOGIN"):
            if not email or not password:
                st.error("Both fields are required!")
            elif check_login(email, password):
                st.session_state.user_email = email
                st.success("Welcome!")
                navigate_to("Survey")
            else:
                st.error("Invalid email or password.")

        st.markdown(
            """
            <div style="text-align: center; font-size: 13px; color: #333;">
                Don’t have an account? 
                <a href="?page=forgot" target="_self" style="color: #007BFF; font-weight: bold;">Forgot Password?</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Click here to Sign Up"):
            navigate_to("User_Registration")

        st.markdown("</div>", unsafe_allow_html=True)

# Example standalone usage for testing
if __name__ == "__main__":
    DatabaseConnection.initialize_pool()

    def dummy_navigate_to(page_name):
        st.success(f"Navigating to {page_name} (dummy)")
        st.stop()

    login(dummy_navigate_to)
