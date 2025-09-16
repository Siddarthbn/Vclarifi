import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import boto3
import json

# ---------- FILE PATHS ----------
bg_path = "images/background.jpg"  # Ensure this path is correct
logo_path = "images/VTARA.png"     # Ensure this path is correct

# --- AWS SECRETS MANAGER HELPER FUNCTION ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    """Fetches application secrets from AWS Secrets Manager and caches them."""
    secret_name = "production/vclarifi/app_secrets"
    region_name = "us-east-1"  # Change to your AWS region if different

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        return json.loads(secret_string)
    except Exception as e:
        st.error(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        return None

# --- DATABASE CONNECTION CLASS WITH POOLING ---
class DatabaseConnection:
    _pool = None

    @classmethod
    def initialize_pool(cls):
        """Initializes the database connection pool."""
        if cls._pool is None:
            secrets = get_aws_secrets()
            if not secrets:
                st.error("Could not load secrets. DB pool failed.")
                return
            try:
                cls._pool = pooling.MySQLConnectionPool(
                    pool_name="vclarifi_pool",
                    pool_size=5,
                    host=secrets.get("DB_HOST"),
                    user=secrets.get("DB_USER"),
                    password=secrets.get("DB_PASSWORD"),
                    database=secrets.get("DB_DATABASE")
                )
            except mysql.connector.Error as err:
                st.error(f"Database connection pool error: {err}")
                cls._pool = None

    @classmethod
    def get_connection(cls):
        """Gets a connection from the pool."""
        if cls._pool is None:
            cls.initialize_pool()
        if cls._pool:
            return cls._pool.get_connection()
        return None

# --- LOGIN CHECK FUNCTION ---
def check_login(email, password):
    """Checks user credentials against the database."""
    conn = None
    cursor = None
    try:
        conn = DatabaseConnection.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("SELECT Password FROM user_registration WHERE Email_Id = %s", (email,))
        result = cursor.fetchone()

        if result and result[0]:
            stored_hashed_password = result[0]
            if isinstance(stored_hashed_password, str):
                stored_hashed_password = stored_hashed_password.encode('utf-8')
            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
                return True
    except mysql.connector.Error as err:
        st.error(f"Database query error: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
    return False


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
                background-attachment: fixed;
            }}
            [data-testid="stHeader"] {{
                background: rgba(0, 0, 0, 0);
            }}
            </style>
        """, unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Background image not found at {image_path}")

def apply_styles():
    st.markdown("""
        <style>
        .left-info {
            color: white;
            font-size: 14px;
            margin-top: 20px;
            padding-left: 60px;
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .login-container {
            background-color: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            width: 400px;
            margin-top: 150px; /* Adjusted margin to position login box lower */
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.2);
        }
        .login-container .stButton > button {
            width: 100%;
            height: 55px;
            font-size: 18px;
            border-radius: 8px;
            background-color: #2c662d;
            color: white;
            border: none;
        }
        .bottom-links {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 14px;
            color: #333;
            margin-top: 15px;
        }
        .bottom-links a {
            color: #007BFF;
            font-weight: bold;
            text-decoration: none;
        }
        .stTextInput > div > div > input {
            height: 55px;
            font-size: 18px;
            border-radius: 8px;
            padding: 10px 15px;
        }
        .top-right-brand {
            position: fixed;
            top: 40px;
            right: 50px;
            font-size: 28px;
            font-weight: bold;
            color: white;
            text-shadow: 2px 2px 4px #000000;
            z-index: 1000;
        }
        </style>
    """, unsafe_allow_html=True)

# ---------- LOGIN PAGE FUNCTION ----------
def login(navigate_to, *args, **kwargs):
    st.set_page_config(layout="wide")

    # Handle navigation from query parameters FIRST
    if "page" in st.query_params:
        page_value = st.query_params.get("page")
        if page_value in ["forgot", "User_Registration"]:
            del st.query_params["page"]
            navigate_to(page_value)
            st.stop() # Stop execution to complete navigation immediately

    set_background(bg_path)
    apply_styles()

    # Add the VCLARIFI text to the top-right corner
    st.markdown('<div class="top-right-brand">VCLARIFI</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        try:
            logo_image = Image.open(logo_path)
            st.image(logo_image, width=300)
            st.markdown("""
            <div class="left-info">
                <div><b>📞 Phone:</b> +123-456-7890</div>
                <div><b>✉️ E-Mail:</b> hello@vclarifi.com</div>
                <div><b>🌐 Website:</b> www.vclarifi.com</div>
                <div><b>📍 Address:</b> Canberra, Australia</div>
            </div>
            """, unsafe_allow_html=True)
        except FileNotFoundError:
            st.error(f"Logo image not found at {logo_path}")

    with col_right:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        st.markdown('<div style="font-size: 32px; font-weight: bold; color: navy; text-align: center; margin-bottom: 25px;">LOGIN TO YOUR ACCOUNT</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email Address", key="email_input")
            password = st.text_input("Password", type="password", key="password_input")
            submitted = st.form_submit_button("LOGIN")

            if submitted:
                if not email or not password:
                    st.error("Both email and password are required!")
                elif check_login(email, password):
                    st.session_state.user_email = email
                    st.success("Welcome!")
                    navigate_to("Survey")
                else:
                    st.error("Invalid email or password.")

        st.markdown("""
            <div class="bottom-links">
                <span>Don’t have an account?</span>
                <a href="?page=forgot" target="_self">Forgot Password?</a>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top:15px;'>", unsafe_allow_html=True)
        if st.button("Click here to Sign Up"):
            navigate_to("User_Registration")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
