import streamlit as st
from PIL import Image
import base64
import mysql.connector
from mysql.connector import pooling
import bcrypt
import boto3
import json

# ---------- FILE PATHS ----------
bg_path = "images/background.jpg"
logo_path = "images/vtara.png"

# --- AWS SECRETS MANAGER HELPER FUNCTION ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    secret_name = "production/vclarifi/app_secrets"
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        return json.loads(secret_string)
    except Exception as e:
        st.error(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        return None

# --- DATABASE CONNECTION WITH POOLING ---
class DatabaseConnection:
    _pool = None

    @classmethod
    def initialize_pool(cls):
        if cls._pool is None:
            secrets = get_aws_secrets()
            if not secrets:
                st.error("❌ Could not load secrets from AWS Secrets Manager.")
                return

            db_secrets = secrets.get("database")
            if not db_secrets:
                st.error("❌ 'database' section is missing in your AWS secrets.")
                return

            required_keys = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_DATABASE"]
            missing_keys = [k for k in required_keys if not db_secrets.get(k)]
            if missing_keys:
                st.error(f"❌ Missing keys in 'database' secret: {', '.join(missing_keys)}")
                return

            try:
                cls._pool = pooling.MySQLConnectionPool(
                    pool_name="vclarifi_pool",
                    pool_size=5,
                    host=db_secrets["DB_HOST"],
                    user=db_secrets["DB_USER"],
                    password=db_secrets["DB_PASSWORD"],
                    database=db_secrets["DB_DATABASE"]
                )
            except mysql.connector.Error as err:
                st.error("❌ MySQL connection pool initialization failed.")
                st.exception(err)
                cls._pool = None

    @classmethod
    def get_connection(cls):
        if cls._pool is None:
            cls.initialize_pool()

        if cls._pool:
            try:
                return cls._pool.get_connection()
            except mysql.connector.Error as err:
                st.error("❌ Could not get DB connection from pool.")
                st.exception(err)
        return None

# --- LOGIN CHECK FUNCTION ---
def check_login(email, password):
    conn = None
    cursor = None
    try:
        conn = DatabaseConnection.get_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("SELECT Password FROM user_registration WHERE Email_Id = %s", (email,))
        result = cursor.fetchone()

        if not result:
            st.warning("⚠️ No user found with this email.")
            return False

        stored_hashed_password = result[0]
        if isinstance(stored_hashed_password, str):
            stored_hashed_password = stored_hashed_password.encode('utf-8')

        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
            return True
        else:
            st.warning("⚠️ Password does not match.")
            return False

    except mysql.connector.Error as err:
        st.error(f"❌ Database query error during login: {err}")
    except Exception as e:
        st.error(f"❌ Unexpected error during login: {e}")
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
                color: white;
            }}
            [data-testid="stHeader"] {{
                background: rgba(0, 0, 0, 0);
            }}
            .stButton>button {{
                width: 100%;
                padding: 15px;
                font-size: 18px;
                border-radius: 8px;
                background-color: #2c662d;
                color: white;
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

# ---------- LOGIN PAGE FUNCTION ----------
def login(navigate_to=None):
    st.set_page_config(layout="wide")

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

        if st.button("LOGIN"):
            if not email or not password:
                st.error("Both fields are required!")
            elif check_login(email, password):
                st.session_state.user_email = email
                st.success("✅ Login successful!")
                if navigate_to:
                    navigate_to("Survey")
            else:
                st.error("❌ Invalid email or password.")

        st.markdown("""
            <div style="text-align: center; font-size: 13px; color: #333;">
                Don’t have an account? 
                <a href="?page=forgot" target="_self" style="color: #007BFF; font-weight: bold;">Forgot Password?</a>
            </div>
        """, unsafe_allow_html=True)

        if st.button("Click here to Sign Up"):
            if navigate_to:
                navigate_to("User_Registration")

        st.markdown('</div>', unsafe_allow_html=True)


# ---------- FOR LOCAL TESTING ----------
if __name__ == '__main__':
    DatabaseConnection.initialize_pool()

    def dummy_navigate_to(page_name):
        st.success(f"Navigating to {page_name} (dummy)")
        st.stop()

    login(dummy_navigate_to)
