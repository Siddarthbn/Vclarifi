import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import logging

# Note: boto3 and json are NOT imported here.

# ---------- FILE PATHS AND CONSTANTS ----------
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"

# ---------- DATABASE CONNECTION (receives secrets) ----------
class DatabaseConnection:
    _pool = None

    @classmethod
    def initialize_pool(cls, secrets):
        if cls._pool is None:
            if not secrets:
                st.error("Database secrets not provided.")
                return
            try:
                cls._pool = pooling.MySQLConnectionPool(
                    pool_name="vclarifi_pool",
                    pool_size=5,
                    host=secrets.get("DB_HOST"),
                    user=secrets.get("DB_USER"),
                    password=secrets.get("DB_PASSWORD"),
                    database=secrets.get("DB_DATABASE"),
                    port=secrets.get("DB_PORT", 3306)
                )
            except mysql.connector.Error as err:
                st.error(f"Database connection pool error: {err}")
                cls._pool = None

    @classmethod
    def get_connection(cls, secrets):
        if cls._pool is None:
            cls.initialize_pool(secrets)
        if cls._pool:
            return cls._pool.get_connection()
        return None

# --- LOGIN CHECK FUNCTION (receives secrets) ---
def check_login(email, password, secrets):
    conn = None
    try:
        conn = DatabaseConnection.get_connection(secrets)
        if not conn: return False
        with conn.cursor() as cursor:
            cursor.execute("SELECT Password FROM user_registration WHERE Email_Id = %s", (email,))
            result = cursor.fetchone()
            if result and result[0]:
                stored_hashed_password = result[0].encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
                    return True
    except mysql.connector.Error as err:
        st.error(f"Database query error: {err}")
    finally:
        if conn and conn.is_connected():
            conn.close()
    return False

# ---------- UI UTILITY FUNCTIONS ----------
def encode_image_to_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        logging.warning(f"Image file not found at {path}.")
        return None

def set_background(image_path):
    encoded = encode_image_to_base64(image_path)
    if encoded:
        st.markdown(f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/jpeg;base64,{encoded}");
                background-size: cover;
            }}
            </style>
        """, unsafe_allow_html=True)

def apply_styles():
    st.markdown("""
        <style>
        .left-info {
            color: white; font-size: 14px; margin-top: 20px;
            padding-left: 60px; line-height: 1.6;
        }
        .login-container {
            background-color: rgba(255, 255, 255, 0.95);
            padding: 40px; border-radius: 20px; width: 400px;
            margin-top: 100px; /* Adjusted margin to remove extra space */
            box-shadow: 0 12px 30px rgba(0,0,0,0.2);
        }
        /* Make all buttons inside the container wider */
        .login-container .stButton > button {
            width: 100%;
            height: 50px;
            font-size: 16px;
        }
        .top-right-brand {
            position: fixed; top: 40px; right: 50px; font-size: 28px;
            font-weight: bold; color: white; text-shadow: 2px 2px 4px #000;
        }
        </style>
    """, unsafe_allow_html=True)

# ---------- LOGIN PAGE MAIN FUNCTION ----------
def login(navigate_to, secrets):
    try:
        st.set_page_config(layout="wide")
    except st.errors.StreamlitAPIException:
        pass # Already set

    set_background(BG_IMAGE_PATH)
    apply_styles()

    st.markdown('<div class="top-right-brand">VCLARIFI</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        # Your logo and contact info display code here...
        pass

    with col_right:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 28px; font-weight: bold; color: navy; text-align: center; margin-bottom: 25px;">LOGIN TO YOUR ACCOUNT</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email Address", key="email_input")
            password = st.text_input("Password", type="password", key="password_input")
            submitted = st.form_submit_button("LOGIN")

            if submitted:
                if not email or not password:
                    st.error("Both fields are required!")
                elif check_login(email, password, secrets):
                    st.session_state.user_email = email
                    st.success("Welcome!")
                    navigate_to("Survey")
                else:
                    st.error("Invalid email or password.")
        
        # This button is now outside the form but styled by the container CSS
        if st.button("Click here to Sign Up"):
            navigate_to("User_Registration")

        st.markdown('</div>', unsafe_allow_html=True)
