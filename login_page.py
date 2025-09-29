import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import logging
import time

# Note: boto3 and json are NOT imported here.

# ---------- FILE PATHS AND CONSTANTS ----------
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"

st.set_page_config(
    page_title="Vclarifi",
    page_icon="images/VTARA.png",
    layout="wide", # Optional: you can change the layout
)


# ---------- DATABASE CONNECTION (receives secrets, uses session_state) ----------
class DatabaseConnection:
    @staticmethod
    def initialize_pool(secrets):
        """Initializes the pool and stores it in session_state."""
        if 'db_pool' not in st.session_state:
            if not secrets:
                st.error("Database secrets not provided.")
                st.session_state.db_pool = None
                return
            try:
                st.session_state.db_pool = pooling.MySQLConnectionPool(
                    pool_name="vclarifi_pool",
                    pool_size=5,
                    host=secrets.get("DB_HOST"),
                    user=secrets.get("DB_USER"),
                    password=secrets.get("DB_PASSWORD"),
                    database=secrets.get("DB_DATABASE"),
                    port=secrets.get("DB_PORT", 3306)
                )
                print("Database connection pool initialized.")
            except mysql.connector.Error as err:
                st.error(f"Database connection pool error: {err}")
                st.session_state.db_pool = None

    @staticmethod
    def get_connection(secrets):
        """Gets a connection from the pool stored in session_state."""
        if 'db_pool' not in st.session_state:
            DatabaseConnection.initialize_pool(secrets)
        
        pool = st.session_state.get('db_pool')
        if pool:
            return pool.get_connection()
        return None

# --- LOGIN CHECK FUNCTION (receives secrets) ---
def check_login(email, password, secrets):
    """Checks user credentials against the database."""
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

# ---------- UI STYLING & UTILITY FUNCTIONS ----------
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
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
            </style>
        """, unsafe_allow_html=True)

def apply_styles():
    st.markdown("""
        <style>
        /* Vertically center content in the right column to prevent scrolling */
        div[data-testid="stHorizontalBlock"] > div:nth-of-type(2) {
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .left-info {
            color: white; font-size: 16px; margin-top: 30px; padding-left: 60px;
            line-height: 2; display: flex; flex-direction: column; gap: 10px;
        }
        .login-container {
            background-color: transparent;
            width: 420px;
            box-shadow: none;
            padding: 0;
        }
        .login-container .stButton > button {
            width: 100%; height: 55px; font-size: 18px; font-weight: bold; border-radius: 10px;
            background-image: linear-gradient(to right, #2c662d, #3a803d);
            color: white; border: none;
        }
        /* Style the "Forgot Password?" button to look like a link */
        .link-button .stButton > button {
            background: none !important;
            border: none !important;
            padding: 0 !important;
            color: #87CEEB !important; /* Light blue */
            text-decoration: none !important;
            font-size: 14px;
            font-weight: bold;
            width: auto !important;
            height: auto !important;
        }
        .link-button .stButton > button:hover {
            text-decoration: underline !important;
            color: white !important;
        }
        .stTextInput input {
            height: 55px; font-size: 16px; border-radius: 10px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
        }
        .stTextInput label {
            color: white !important;
            font-weight: bold !important;
        }
        .top-right-brand {
            position: fixed; top: 40px; right: 50px; font-size: 32px;
            font-weight: bold; color: white; text-shadow: 2px 2px 5px #000;
        }
        </style>
    """, unsafe_allow_html=True)

# ---------- LOGIN PAGE MAIN FUNCTION ----------
def login(navigate_to, secrets):
    """ Renders the login page. """
    try:
        st.set_page_config(layout="wide")
    except st.errors.StreamlitAPIException:
        pass # Already set

    set_background(BG_IMAGE_PATH)
    apply_styles()

    st.markdown('<div class="top-right-brand">VCLARIFI</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1.2, 1])

    with col_left:
        try:
            logo_image = Image.open(LOGO_IMAGE_PATH)
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
            st.error(f"Logo image not found at {LOGO_IMAGE_PATH}")

    with col_right:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # Title color changed back to 'navy' as requested
        st.markdown('<div style="font-size: 32px; font-weight: bold; color: navy; text-align: center; margin-bottom: 25px;">LOGIN TO YOUR ACCOUNT</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email Address", key="email_input")
            password = st.text_input("Password", type="password", key="password_input")
            submitted = st.form_submit_button("LOGIN")

            if submitted:
                with st.spinner("Authenticating..."):
                    if not email or not password:
                        st.error("Both email and password are required!")
                    elif check_login(email, password, secrets):
                        st.session_state.user_email = email
                        st.success("Welcome!")
                        time.sleep(0.5)
                        navigate_to("Survey")
                    else:
                        st.error("Invalid email or password.")

        # --- REFINED BOTTOM LINKS ---
        # Using columns to place Sign Up and Forgot Password on the same line
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        col_signup, col_forgot = st.columns([2, 1])

        with col_signup:
            st.markdown("<div style='color: white;'>Don't have an account?</div>", unsafe_allow_html=True)
            if st.button("Click here to Sign Up"):
                navigate_to("User_Registration")

        with col_forgot:
            st.markdown('<div class="link-button" style="text-align: right;">', unsafe_allow_html=True)
            if st.button("Forgot Password?"):
                navigate_to("forgot")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
