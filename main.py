# main.py
import streamlit as st
import importlib # Using importlib for more robust imports

# -------------------- Initialize Session State --------------------
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'  # Default to login page

if 'user_email' not in st.session_state:
    st.session_state.user_email = None  # Store user_email in session_state

# -------------------- Page Navigation Function --------------------
def navigate_to(page_name):
    """Sets the current page in session state and reruns the app."""
    st.session_state.current_page = page_name
    st.rerun()

# -------------------- Page Loader --------------------
def load_page():
    """Loads and displays the current page based on session state."""
    page_key = st.session_state.current_page
    user_email = st.session_state.get('user_email')

    page_modules = {
        'login': {'module_name': 'login_page', 'function_name': 'login', 'requires_login': False},
        'User_Registration': {'module_name': 'user_registration', 'function_name': 'user_registration_entrypoint', 'requires_login': False},
        'Team_Member_Registration': {'module_name': 'user_registration_2', 'function_name': 'render_team_member_registration_view', 'requires_login': False},
        'Consultant_Registration': {'module_name': 'consultant_registration', 'function_name': 'render_consultant_registration_view', 'requires_login': False},
        'forgot': {'module_name': 'forgot', 'function_name': 'render_forgot_password_page', 'requires_login': False},
        'Survey': {'module_name': 'survey', 'function_name': 'survey', 'requires_login': True},
        'Dashboard': {'module_name': 'dashboard', 'function_name': 'dashboard', 'requires_login': True},
        'Recommendations': {'module_name': 'recommendations', 'function_name': 'recommendations_page', 'requires_login': True},
        'VClarifi_Agent': {'module_name': 'vclarifi_agent', 'function_name': 'vclarifi_agent', 'requires_login': False},
        'docbot': {'module_name': 'docbot', 'function_name': 'docbot', 'requires_login': False},
        'text_2_video_agent': {'module_name': 'text_2_video_agent', 'function_name': 'text_2_video_agent', 'requires_login': False},
    }

    page_info = page_modules.get(page_key)

    if page_info is None:
        st.error(f"🚫 Page '{page_key}' not found! Please check the navigation links.")
        if st.button("Go to Login"):
            navigate_to('login')
        return

    if page_info['requires_login'] and not user_email:
        st.warning("🚫 You must be logged in to view this page.")
        if st.button("Go to Login"):
            navigate_to('login')
        return

    try:
        # Dynamically import the module
        # Assumes files like 'forgot.py', 'login_page.py' exist in the same directory or Python path
        module = importlib.import_module(page_info['module_name'])
        # Get the function from the imported module
        page_function = getattr(module, page_info['function_name'])

        # Call the function with appropriate arguments
        if page_info['requires_login']:
            page_function(navigate_to, user_email) # navigate_to is from main.py
        else:
            # For login, User_Registration, Consultant_Registration, forgot, and other non-login pages
            page_function(navigate_to) # navigate_to is from main.py

    except ImportError:
        st.error(f"🚫 Error: Could not import page module '{page_info['module_name']}'. Ensure the file '{page_info['module_name']}.py' exists and is in the Python path.")
    except AttributeError:
        st.error(f"🚫 Error: Could not find function '{page_info['function_name']}' in module '{page_info['module_name']}'. Check the function name in both main.py and the module file.")
    except Exception as e:
        st.error(f"🚫 An unexpected error occurred loading page '{page_key}': {str(e)}")
        # For more detailed debugging during development, you might uncomment the following:
        # import traceback
        # st.error(traceback.format_exc())

# -------------------- Run App --------------------
if __name__ == "__main__":
    # You can set a global page config here if desired for all pages.
    # Example: st.set_page_config(layout="wide", page_title="VClarifi App")
    # However, individual pages might also set their own config if this is not set.
    # If not set here, ensure each page (like login.py, forgot.py) calls st.set_page_config if needed.
    load_page()