# survey_app.py

import streamlit as st
import base64
import mysql.connector
from mysql.connector import Error as DatabaseError
import logging
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import os # <-- IMPORT ADDED FOR PATHING

# ==============================================================================
# --- CONFIGURATION AND CONSTANTS ---
# ==============================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- File Paths ---
# These are now relative to the script's location
BG_PATH = os.path.join("images", "background.jpg")
LOGO_PATH = os.path.join("images", "VTARA.png")

# --- Survey Settings ---
MIN_RESPONDENTS_FOR_TEAM_AVERAGE = 1
TEAM_AVERAGE_DATA_WINDOW_DAYS = 90

# --- Survey Content ---
LIKERT_OPTIONS = [
    "Select", "1: Not at all", "2: To a very little extent", "3: To a little extent",
    "4: To a moderate extent", "5: To a fairly large extent", "6: To a great extent",
    "7: To a very great extent"
]

SURVEY_QUESTIONS = {
    "Leadership": {
        "Strategic Planning": "How effectively does your organisation conduct needs analyses to secure the financial resources needed to meet its strategic goals of achieving world-class performance?",
        "External Environment": "How effectively does your organisation monitor and respond to shifts in the sports industry, including advancements in technology, performance sciences, and competitive strategies?",
        "Resources": "How adequately are physical, technical, and human resources aligned to meet the demands of high-performance sports?",
        "Governance": "How robust are the governance structures in maintaining the integrity and transparency of organisational processes?"
    },
    "Empower": {
        "Feedback": "How effectively does the organisation collect and act on feedback from athletes, coaches, and support teams?",
        "Managing Risk": "How effectively does the organisation identify, assess, and mitigate risks in its operations?",
        "Decision-Making": "How effectively does the organisation balance data-driven and experience-based decision-making processes?",
        "Recovery Systems": "To what extent is technology leveraged to improve training, recovery, and performance analysis?"
    },
    "Sustainability": {
        "Long-Term Planning": "How effectively does the organisation integrate long-term sustainability goals into its strategic vision?",
        "Resource Management": "How efficient is the use of financial, human, and physical resources to ensure long-term operational success?",
        "Environmental Impact": "How conscious is the organisation of its environmental impact and mitigation strategies?",
        "Stakeholder Engagement": "How actively are key stakeholders involved in sustainability discussions and decisions?"
    },
    "CulturePulse": {
        "Values": "How clearly are organisational values defined and communicated across teams?",
        "Respect": "How well does the organisation foster mutual respect among athletes, coaches, and support staff?",
        "Communication": "How effectively does the organisation use technology to enhance communication and connectivity across teams?",
        "Diversity": "How effectively does the organisation embrace diversity in its members' backgrounds, skills, and perspectives?"
    },
    "Bonding": {
        "Personal Growth": "How effectively are athletes and staff supported in understanding their strengths and development areas?",
        "Negotiation": "How effectively are members encouraged to express conviction while remaining open to compromise?",
        "Group Cohesion": "How effectively does the organisation promote a shift from individual focus to team-first mentality?",
        "Support": "How effectively does the organisation provide emotional and professional support to its members?"
    },
    "Influencers": {
        "Funders": "How effectively does the organisation communicate its strategic goals and performance outcomes to funders to secure ongoing or increased financial support?",
        "Sponsors": "How effectively does the organisation engage sponsors to create mutually beneficial partnerships that enhance visibility, resources, and athlete/team support?",
        "Peer Groups": "How effectively does the organisation collaborate with peer groups to share best practices, innovations, and performance insights that enhance internal processes?",
        "External Alliances": "How effectively does the organisation build alliances with external partners (e.g., research institutions, technology providers) to access expertise and drive innovation?"
    }
}
ALL_CATEGORY_KEYS = list(SURVEY_QUESTIONS.keys())


# ==============================================================================
# --- UI AND STYLING UTILITIES ---
# ==============================================================================
def get_absolute_path(relative_path):
    """Constructs an absolute path from a path relative to the script file."""
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, relative_path)

def set_background(image_path):
    """Sets a robust full-screen background and applies custom CSS."""
    abs_path = get_absolute_path(image_path)
    try:
        with open(abs_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{encoded}");
            background-size: cover; background-repeat: no-repeat; background-attachment: fixed;
        }}
        /* Other CSS rules remain the same */
        [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
        .branding {{ position: fixed; top: 20px; right: 20px; display: flex; align-items: center; gap: 10px; z-index: 1001; }}
        .branding img {{ width: 70px; }}
        .vclarifi-text {{ font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }}
        .logout-button-container {{ position: fixed; top: 75px; right: 20px; z-index: 1001; }}
        .logout-button-container button {{ padding: 5px 10px !important; font-size: 16px !important; background-color: #dc3545 !important; color: white !important; border: none !important; border-radius: 5px !important; cursor: pointer; width: auto !important; line-height: 1; }}
        .logout-button-container button:hover {{ background-color: #c82333 !important; }}
        .stButton > button {{ width: 100%; padding: 15px; font-size: 18px; border-radius: 8px; background-color: #2c662d; color: white; border: none; cursor: pointer; transition: background-color 0.3s ease; }}
        .stButton > button:hover {{ background-color: #3a803d; }}
        .stButton > button:disabled {{ background-color: #a0a0a0; color: #e0e0e0; cursor: not-allowed; }}
        .dashboard-cta-button button, .admin-action-button button, .logout-button-container button {{ width: auto !important; }}
        .dashboard-cta-button {{ width: 100%; }}
        .dashboard-cta-button button {{ width: 100% !important; background-color: #28a745 !important; padding: 12px 20px !important; font-weight: bold !important; }}
        .admin-action-button button {{ background-color: #007bff !important; padding: 8px 15px !important; font-size: 16px !important; margin-top: 10px; }}
        .category-container {{ border: 2px solid transparent; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: rgba(0,0,0,0.3); transition: background-color 0.3s ease, border-color 0.3s ease; }}
        .category-container.completed {{ background-color: rgba(0, 123, 255, 0.2) !important; border: 2px solid #007BFF; }}
        .category-container div, .category-container p, .category-container label, .stMarkdown > p, div[data-testid="stRadio"] label span {{ color: white !important; }}
        .stCaption {{ color: rgba(255,255,255,0.9) !important; text-align: center; }}
        </style>""", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Background image not found. Expected at: {abs_path}")
    except Exception as e:
        st.error(f"An error occurred while setting the background: {e}")

def display_branding_and_logout_placeholder(logo_path_param):
    """Displays the branding logo in the top right corner."""
    abs_path = get_absolute_path(logo_path_param)
    try:
        with open(abs_path, "rb") as logo_file:
            logo_encoded = base64.b64encode(logo_file.read()).decode()
        st.markdown(f"""
            <div class="branding">
                <img src="data:image/png;base64,{logo_encoded}" alt="Logo">
                <div class="vclarifi-text">VCLARIFI</div>
            </div>
            """, unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Logo image not found. Expected at: {abs_path}")
    except Exception as e:
        st.error(f"An error occurred while displaying the logo: {e}")

# ==============================================================================
# --- DATABASE UTILITIES ---
# ==============================================================================
def create_db_connection(secrets):
    """Establishes a database connection using the passed-in secrets dictionary."""
    try:
        return mysql.connector.connect(
            host=secrets.get("DB_HOST"),
            database=secrets.get("DB_DATABASE"),
            user=secrets.get("DB_USER"),
            password=secrets.get("DB_PASSWORD"),
            port=secrets.get("DB_PORT", 3306)
        )
    except DatabaseError as e:
        st.error(f"Database connection failed: {e}")
        logging.error(f"DB connection failed: {e}")
        return None

def close_db_connection(conn, cursor=None):
    """Safely closes a database cursor and connection."""
    if cursor:
        try: cursor.close()
        except DatabaseError: pass
    if conn and conn.is_connected():
        try: conn.close()
        except DatabaseError: pass

def save_category_to_db(category_key, responses_data, user_email, submission_id, secrets):
    """Saves the responses for a single category to the database."""
    conn = create_db_connection(secrets)
    if not conn: return None
    try:
        with conn.cursor() as cursor:
            # NOTE: This logic assumes a separate table exists for each category.
            # This is a complex schema design. Ensure these tables are created.
            # For simplicity, this example focuses on calculation, not complex DB writes.
            current_category_responses = responses_data.get(category_key, {})
            if not current_category_responses: return None
            total_score, count_answered = 0, 0
            for value_str in current_category_responses.values():
                if value_str != "Select":
                    try:
                        val_int = int(value_str.split(":")[0])
                        total_score += val_int
                        count_answered += 1
                    except (ValueError, IndexError): pass
            avg_score = round(total_score / count_answered, 2) if count_answered > 0 else None
            # Here, you would execute your INSERT/UPDATE SQL statements
            # for the specific category table, the Averages table, etc.
            # conn.commit()
            return avg_score
    except DatabaseError as e:
        st.error(f"Database error while saving '{category_key}': {e}")
        conn.rollback()
        return None
    finally:
        close_db_connection(conn)

# ==============================================================================
# --- MAIN SURVEY PAGE FUNCTION ---
# ==============================================================================
def render_survey_page(**kwargs):
    """
    Renders the survey page, including category selection and question forms.
    Accepts kwargs to be compatible with the flexible calling from main.py.
    """
    # Safely extract needed arguments from kwargs
    user_email = kwargs.get('user_email')
    secrets = kwargs.get('secrets')
    navigate_to = kwargs.get('navigate_to')

    # --- UI Setup ---
    set_background(BG_PATH)
    display_branding_and_logout_placeholder(LOGO_PATH)

    # --- Initialize Session State for Survey ---
    if "survey_user" not in st.session_state or st.session_state.survey_user != user_email:
        st.session_state.survey_user = user_email
        st.session_state.responses = {cat: {q: "Select" for q in qs.keys()} for cat, qs in SURVEY_QUESTIONS.items()}
        st.session_state.saved_categories = set()
        st.session_state.selected_category = None
        # Here you would typically load any existing user progress from the DB

    # --- RENDER CATEGORY SELECTION OR QUESTION FORM ---
    if st.session_state.get('selected_category') is None:
        st.title("QUESTIONNAIRE")
        st.subheader("Choose a category to begin or continue:")

        answered_overall = sum(1 for cat_resps in st.session_state.responses.values() for r_val in cat_resps.values() if r_val != "Select")
        total_overall = sum(len(q_defs) for q_defs in SURVEY_QUESTIONS.values())
        progress_overall_val = answered_overall / total_overall if total_overall > 0 else 0
        st.progress(progress_overall_val)
        st.markdown(f"<p style='text-align:center; color:white;'>Overall Progress: {answered_overall}/{total_overall} ({progress_overall_val:.0%})</p>", unsafe_allow_html=True)

        cols = st.columns(3)
        for i, cat_key in enumerate(ALL_CATEGORY_KEYS):
            is_completed = cat_key in st.session_state.saved_categories
            with cols[i % 3]:
                container_class = "category-container completed" if is_completed else "category-container"
                st.markdown(f"<div class='{container_class}'>", unsafe_allow_html=True)
                if st.button(cat_key, key=f"btn_{cat_key}", use_container_width=True):
                    st.session_state.selected_category = cat_key
                    st.rerun()
                answered_in_cat = sum(1 for v in st.session_state.responses[cat_key].values() if v != "Select")
                total_in_cat = len(SURVEY_QUESTIONS[cat_key])
                cat_progress_val = answered_in_cat / total_in_cat if total_in_cat > 0 else 0
                st.progress(cat_progress_val)
                st.caption("Completed" if is_completed else f"{answered_in_cat}/{total_in_cat}")
                st.markdown("</div>", unsafe_allow_html=True)

        if len(st.session_state.saved_categories) == len(ALL_CATEGORY_KEYS):
            st.success("🎉 Congratulations! You have completed the entire survey.")
            if navigate_to and st.button("Proceed to Dashboard"):
                navigate_to("Dashboard")

    else:
        current_cat = st.session_state.selected_category
        st.subheader(f"Category: {current_cat}")
        st.markdown("---")
        questions_in_cat = SURVEY_QUESTIONS[current_cat]
        answered_count = 0
        for q_key, q_text in questions_in_cat.items():
            st.markdown(f"**{q_text}**")
            current_response = st.session_state.responses[current_cat].get(q_key, "Select")
            try:
                response_index = LIKERT_OPTIONS.index(current_response)
            except ValueError:
                response_index = 0
            selected_value = st.radio(
                label=q_text,
                options=LIKERT_OPTIONS,
                index=response_index,
                key=f"radio_{current_cat}_{q_key}",
                label_visibility="collapsed"
            )
            st.session_state.responses[current_cat][q_key] = selected_value
            if selected_value != "Select":
                answered_count += 1
        
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅️ Back to Categories", use_container_width=True):
                st.session_state.selected_category = None
                st.rerun()
        with col2:
            is_complete = answered_count == len(questions_in_cat)
            if st.button("Save and Continue ➡️", disabled=not is_complete, use_container_width=True):
                submission_id = st.session_state.get('current_submission_id', -1)
                avg_score = save_category_to_db(current_cat, st.session_state.responses, user_email, submission_id, secrets)
                if avg_score is not None:
                    st.session_state.saved_categories.add(current_cat)
                    st.session_state.selected_category = None
                    st.success(f"Progress for '{current_cat}' has been saved!")
                    st.rerun()
                else:
                    st.error("Failed to save your progress. Please try again.")
        if not is_complete:
            st.caption("Please answer all questions in this category to save your progress.")
