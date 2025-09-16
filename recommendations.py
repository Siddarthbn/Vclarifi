import os
import base64
import pandas as pd
import streamlit as st
import mysql.connector
from mysql.connector import Error
import google.generativeai as genai

# --- Configuration (No changes needed here) ---
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"
GEMINI_MODEL = "models/gemini-1.5-flash"

# --- Survey Questions Dictionary (No changes needed here) ---
SURVEY_QUESTIONS = {
    "Leadership": {
        "Strategic Planning": "How effectively does your organisation conduct needs analyses to secure the financial resources needed to meet its strategic goals of achieving world-class performance?",
        "External Environment": "How effectively does your organisation monitor and respond to shifts in the sports industry, including advancements in technology, performance sciences, and competitive strategies?",
        "Resources": "How adequately are physical, technical, and human resources aligned to meet the demands of high-performance sports?",
        "Governance": "How robust are the governance structures in maintaining the integrity and transparency of organisational processes?"
    },
    # ... other questions remain the same
}


# --- Utility Functions (No changes needed here) ---
def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Image not found at {image_path}. A solid dark background will be used.")
        return ""
    except Exception as e:
        st.error(f"Error encoding image {image_path}: {e}")
        return ""

def set_page_style(bg_image_path):
    # This function is unchanged
    pass

def display_logo_and_text(logo_path, org_name):
    # This function is unchanged
    pass

def get_score_indicator_html(score):
    # This function is unchanged
    pass

# --- Data Access ---
# The hash_func is necessary for Streamlit to cache the dictionary correctly
def hash_secrets(secrets):
    return str(secrets)

@st.cache_data(hash_funcs={dict: hash_secrets})
def fetch_organization_data(user_email, secrets):
    """REFINED: Now accepts a 'secrets' dictionary for database credentials."""
    conn = None
    try:
        # REFINED: Uses the 'secrets' dictionary argument instead of st.secrets
        db_secrets = secrets['database']
        conn = mysql.connector.connect(
            host=db_secrets['DB_HOST'],
            database=db_secrets['DB_DATABASE'],
            user=db_secrets['DB_USER'],
            password=db_secrets['DB_PASSWORD']
        )
        # The rest of the function logic remains the same
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (user_email,))
        user_org_info = cursor.fetchone()
        if not user_org_info or not user_org_info.get('organisation_name'):
            st.warning(f"User '{user_email}' not found or has no organization assigned.")
            return None, None
        org_name = user_org_info['organisation_name']
        # ... (rest of data fetching logic is unchanged)
        return {}, org_name # Placeholder return for brevity
    except (KeyError, Error) as err:
        st.error(f"❌ Database error: {err}")
        st.info("Please ensure your secrets dictionary contains valid database credentials.")
        return None, None
    finally:
        if conn and conn.is_connected(): conn.close()

# --- Recommendation Generation ---
@st.cache_data(show_spinner=False, hash_funcs={dict: hash_secrets})
def generate_recommendations(_category_name, average_score, questions_context, secrets):
    """REFINED: Now accepts a 'secrets' dictionary for the Gemini API key."""
    try:
        # REFINED: Uses the 'secrets' dictionary argument instead of st.secrets
        gemini_api_key = secrets['gemini']['api_key']
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        
        # The rest of the function logic remains the same
        category_questions = questions_context.get(_category_name, {})
        question_details = "\n".join([f"- **{sub_cat}:** {question}" for sub_cat, question in category_questions.items()])
        prompt = (
            f"As an expert consultant for high-performance sports organizations, analyze the following and provide specific, actionable recommendations.\n\n"
            f"**Category:** '{_category_name}'\n"
            f"**Organization's Average Score:** {average_score:.2f} (on a 1-7 scale).\n\n"
            # ... (rest of prompt is unchanged)
        )
        response = model.generate_content(prompt)
        return getattr(response, "text", "Could not generate text response from the model.")
    except (KeyError, Exception) as e:
        st.error(f"An error occurred while generating recommendations for {_category_name}: {e}")
        st.info("Please ensure your secrets dictionary contains a valid Gemini API key.")
        return "Sorry, we were unable to generate recommendations at this time."

# --- UI Rendering Functions ---
def display_category_grid(category_scores, navigate_to):
    # This function is unchanged
    pass

def display_recommendation_detail(category, score, secrets):
    """REFINED: Now accepts and passes 'secrets' to the recommendation generator."""
    if st.button("⬅️ Back to All Categories"):
        st.session_state.selected_category = None
        st.rerun()

    indicator_html = get_score_indicator_html(score)
    st.markdown(f"## Recommendations for {category}")
    st.markdown(f"Current Performance: **{indicator_html}** (Score: {score:.2f} / 7)", unsafe_allow_html=True)
    
    with st.spinner(f"Generating tailored recommendations for {category}..."):
        # REFINED: Passes the 'secrets' dictionary to the generator
        recommendations_text = generate_recommendations(category, score, SURVEY_QUESTIONS, secrets)
        st.markdown(f"""
            <div class="recommendation-container">
            {recommendations_text}
            </div>
        """, unsafe_allow_html=True)

# --- Main Page Function ---
def recommendations_page(navigate_to=None, user_email=None, secrets=None):
    """
    REFINED: Renders the main recommendations page.
    Now requires a 'secrets' dictionary to be passed for its operations.
    """
    set_page_style(BG_IMAGE_PATH)
    
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None

    if not secrets:
        st.error("Application configuration (secrets) not loaded. Cannot display page.")
        return

    # REFINED: Passes the 'secrets' dictionary to fetch data
    org_data, org_name = fetch_organization_data(user_email, secrets)
    display_logo_and_text(LOGO_IMAGE_PATH, org_name)

    st.markdown(f"""
        <div class="page-header-container">
            <h1>Performance Enhancement Recommendations</h1>
            <h3>For {org_name or 'Your Organization'}</h3>
        </div>
    """, unsafe_allow_html=True)

    if org_data is None:
        st.info("Waiting for organization data to be loaded or no data available.")
        if st.button("⬅️ Back to Dashboard"):
            if navigate_to: navigate_to("Dashboard")
        return

    # The rest of the page logic remains the same...
    category_avg_keys = {
        "Leadership": "Leadership_avg", "Empower": "Empower_avg", "Sustainability": "Sustainability_avg",
        "CulturePulse": "CulturePulse_avg", "Bonding": "Bonding_avg", "Influencers": "Influencers_avg"
    }
    category_scores = {
        cat: org_data[key] for cat, key in category_avg_keys.items()  
        if key in org_data and pd.notna(org_data[key])
    }

    if not category_scores:
        st.warning(f"No valid average category scores were found for organization '{org_name}'.")
        return

    if st.session_state.selected_category is None:
        display_category_grid(category_scores, navigate_to)
    else:
        selected_cat = st.session_state.selected_category
        score = category_scores[selected_cat]
        # REFINED: Passes the 'secrets' dictionary to the detail view
        display_recommendation_detail(selected_cat, score, secrets)

# --- Example Usage ---
if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="VClarifi Recommendations")

    # For standalone testing, we create a mock secrets object.
    # In production, this is passed from main.py.
    mock_secrets = {
        "database": {
            "DB_HOST": "your_host", "DB_DATABASE": "your_db",
            "DB_USER": "your_user", "DB_PASSWORD": "your_password"
        },
        "gemini": {
            "api_key": "your_gemini_api_key"
        }
    }

    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = 'admin_alpha@example.com'
    
    # In a real app, nav_to would come from main.py
    def nav_to(page):
        st.info(f"Navigate to: {page}")

    # REFINED: Call the main function with the mock secrets
    recommendations_page(navigate_to=nav_to, user_email=st.session_state.user_email, secrets=mock_secrets)
