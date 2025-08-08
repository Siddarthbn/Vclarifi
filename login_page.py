import streamlit as st
from PIL import Image
import base64
import mysql.connector
import bcrypt

# ---------- FILE PATHS ----------
bg_path = "C:/Users/DELL/Desktop/background.jpg"  # Ensure this path is correct
logo_path = "C:/Users/DELL/Desktop/VTARA.png"    # Ensure this path is correct

# ---------- DATABASE CONNECTION ----------
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="vclarifi",
            password="Siddarth@99", # Consider using environment variables or Streamlit secrets for credentials
            database="VClarifi"
        )
    except mysql.connector.Error as err:
        st.error(f"Database connection error: {err}")
        return None

def check_login(email, password):
    conn = get_db_connection()
    if not conn:
        return False # DB connection failed

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT Password FROM user_registration WHERE Email_Id = %s", (email,))
        result = cursor.fetchone()
        if result and result[0]: # Check if result and password are not None
            stored_hashed_password = result[0]
            # Ensure both are bytes for bcrypt.checkpw
            if isinstance(stored_hashed_password, str):
                stored_hashed_password = stored_hashed_password.encode('utf-8')
            
            if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password):
                return True
    except mysql.connector.Error as err:
        st.error(f"Login error: {err}")
    except Exception as e: # Catch other potential errors, e.g., with encoding or bcrypt
        st.error(f"An unexpected error occurred during login: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected(): # Ensure connection exists and is open before closing
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

# ---------- LOGIN FUNCTION ----------
def login(navigate_to):
    # st.set_page_config() must be the first Streamlit command executed, and only once per page.
    # If this 'login' function defines the entire view/page, this is the correct place.
    st.set_page_config(layout="wide")

    # Handle navigation triggered by URL query parameters
    # This check should occur early, before rendering the bulk of the page.
    if "page" in st.query_params:
        page_value = st.query_params.get("page")
        if page_value == "forgot":
            # Clear the 'page' query parameter to prevent re-navigation on subsequent script reruns or page refresh.
            # This modifies st.query_params for the current script run and schedules a URL update for the browser.
            del st.query_params["page"]
            
            # Call the provided navigation function to switch to the "forgot password" page/view
            navigate_to("forgot") 
            return  # Exit this function to prevent rendering the login page

    set_background(bg_path)
    apply_styles()

    col_left, col_right = st.columns([1.2, 1])

    # ---------- LEFT PANEL ----------
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

    # ---------- RIGHT PANEL ----------
    with col_right:
        st.markdown("""
        <div style="position: relative; margin-bottom: 20px; text-align: right;">
            <div style="font-size: 40px; font-weight: bold; color: #ffffff;">
                VCLARIFI
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        st.markdown("""
            <div style="font-size: 32px; font-weight: bold; color: navy; text-align: center;">
                LOGIN TO YOUR ACCOUNT
            </div>
        """, unsafe_allow_html=True)

        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")

        if st.button("LOGIN"):
            if not email or not password:
                st.error("Both fields are required!")
            elif check_login(email, password):
                st.session_state.user_email = email # Store user's email in session state
                st.success("Welcome!")
                navigate_to("Survey")  # Navigate to the Survey page
            else:
                st.error("Invalid email or password.")

        # Modified "Forgot Password?" link:
        # - href now points to "?page=forgot" to set a URL query parameter.
        # - target="_self" ensures it opens in the same tab.
        st.markdown("""
            <div style="text-align: center; font-size: 13px; color: #333;">
                Don’t have an account? 
                <a href="?page=forgot" target="_self" style="color: #007BFF; font-weight: bold;">Forgot Password?</a>
            </div>
        """, unsafe_allow_html=True)

        if st.button("Click here to Sign Up"):
            navigate_to("User_Registration") # Navigate to User Registration page

        st.markdown('</div>', unsafe_allow_html=True)

# Example of how you might call this login function (if it's part of a larger app)
# def app():
#     # This function would be your app's main router, deciding which "page" to show.
#     # 'navigate_to' would be a function that changes st.session_state.current_page (or similar)
#     # and then calls st.experimental_rerun() or lets Streamlit rerun naturally.
#     
#     # Placeholder for navigate_to function
#     def navigate(page_name):
#         st.session_state.current_page = page_name
#         # In a real multipage app, you might clear query params here or rely on st.experimental_rerun()
#         if "page" in st.query_params: # Example of specific cleanup if desired
#             del st.query_params['page']
#         st.rerun() # Use st.rerun() for modern Streamlit versions
#
#     if 'current_page' not in st.session_state:
#         st.session_state.current_page = 'login'
#
#     # Initial query param check could also be here at the app's entry point
#     if "page" in st.query_params and st.query_params.get("page") == "forgot" and st.session_state.current_page != "forgot_redirecting":
#         # Temporary state to handle redirect
#         st.session_state.current_page = "forgot_redirecting" 
#         del st.query_params["page"]
#         navigate("forgot") # This will cause a rerun, and the next block will catch 'forgot'
#         return
#
#     if st.session_state.current_page == 'login':
#         login(navigate)
#     elif st.session_state.current_page == 'Survey':
#         st.title("Survey Page") # Placeholder for Survey page content
#         # survey_page_function(navigate) 
#     elif st.session_state.current_page == 'User_Registration':
#         st.title("User Registration Page") # Placeholder
#         # registration_page_function(navigate)
#     elif st.session_state.current_page == 'forgot':
#         st.title("Forgot Password Page") # Placeholder for forgot.py content
#         # forgot_password_page_function(navigate)
#
# if __name__ == '__main__':
#     # If this script is run directly as the login page:
#     # Define a dummy navigate_to or integrate with your actual multi-page logic.
#     def dummy_navigate_to(page_name):
#         st.success(f"Navigating to {page_name} (dummy)")
#         if page_name == "forgot":
#             # In a real scenario, this would load forgot.py's content
#             st.markdown("## Forgot Password Page Content (from forgot.py)") 
#             st.stop() # Stop further execution if navigation means showing a new page here
#         elif page_name == "Survey":
#             st.markdown("## Survey Page Content")
#             st.stop()
#         elif page_name == "User_Registration":
#             st.markdown("## User Registration Page Content")
#             st.stop()

#     login(dummy_navigate_to)
#
#     # If part of a larger app structure, you would call something like app()
#     # app()