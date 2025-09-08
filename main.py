import streamlit as st
import importlib

# Initialize session state variables
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'  # default page

if 'user_email' not in st.session_state:
    st.session_state.user_email = None

def navigate_to(page_name):
    """Change page and rerun app"""
    st.session_state.current_page = page_name
    st.experimental_rerun()  # st.rerun() was deprecated

def load_page():
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
        st.error(f"🚫 Page '{page_key}' not found!")
        if st.button("Go to Login"):
            navigate_to('login')
        return

    if page_info['requires_login'] and not user_email:
        st.warning("🚫 You must be logged in to view this page.")
        if st.button("Go to Login"):
            navigate_to('login')
        return

    module_name = page_info['module_name']
    function_name = page_info['function_name']

    try:
        # Debug print
        print(f"Importing module '{module_name}' and calling function '{function_name}'")

        module = importlib.import_module(module_name)
        page_function = getattr(module, function_name)

        if page_info['requires_login']:
            page_function(navigate_to, user_email)
        else:
            page_function(navigate_to)

    except ModuleNotFoundError as mnfe:
        st.error(f"🚫 Module '{module_name}' not found. Make sure '{module_name}.py' exists in the project folder.")
        st.error(str(mnfe))
    except AttributeError as ae:
        st.error(f"🚫 Function '{function_name}' not found in module '{module_name}'.")
        st.error(str(ae))
    except Exception as e:
        st.error(f"🚫 Unexpected error loading page '{page_key}': {e}")
        # Uncomment below for full traceback during development:
        # import traceback
        # st.error(traceback.format_exc())

if __name__ == "__main__":
    load_page()
