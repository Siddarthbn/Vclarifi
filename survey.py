# survey.py

import streamlit as st
import base64
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
import numpy as np
import logging
import boto3
import json

# ======================================================================================
# CONFIGURATION & INITIALIZATION
# ======================================================================================

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- AWS Secrets Manager Integration ---
@st.cache_data(ttl=600)
def get_aws_secrets():
    """Fetches secrets from AWS Secrets Manager and caches them."""
    secret_name = "production/vclarifi/secrets"
    region_name = "us-east-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        logging.info("Secrets Loaded Successfully from AWS.")
        return json.loads(secret_string)
    except Exception as e:
        logging.critical(f"FATAL: Could not retrieve application secrets from AWS. Error: {e}")
        st.error("FATAL: Could not retrieve application secrets. Please contact an administrator.")
        return None

# --- Global Configuration (Robust Startup) ---
try:
    aws_secrets = get_aws_secrets()
    if aws_secrets:
        DB_HOST = aws_secrets.get('DB_HOST')
        DB_DATABASE = aws_secrets.get('DB_DATABASE')
        DB_USER = aws_secrets.get('DB_USER')
        DB_PASSWORD = aws_secrets.get('DB_PASSWORD')
        SENDER_EMAIL = aws_secrets.get('SENDER_EMAIL')
        SENDER_APP_PASSWORD = aws_secrets.get('SENDER_APP_PASSWORD')
        SMTP_SERVER = aws_secrets.get('SMTP_SERVER')
        SMTP_PORT = aws_secrets.get('SMTP_PORT')
        
        CONFIG_LOADED_SUCCESSFULLY = all([DB_HOST, DB_DATABASE, DB_USER, DB_PASSWORD, SENDER_EMAIL, SENDER_APP_PASSWORD, SMTP_SERVER, SMTP_PORT])
        if not CONFIG_LOADED_SUCCESSFULLY:
            logging.critical("FATAL: One or more essential secrets are missing from the AWS payload.")
    else:
        CONFIG_LOADED_SUCCESSFULLY = False
except Exception as e:
    logging.critical(f"FATAL: An unexpected error occurred during secrets processing. Error: {e}")
    CONFIG_LOADED_SUCCESSFULLY = False

if not CONFIG_LOADED_SUCCESSFULLY:
    DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
    SENDER_EMAIL = SENDER_APP_PASSWORD = SMTP_SERVER = SMTP_PORT = None

# ======================================================================================
# DATABASE HELPER FUNCTIONS
# ======================================================================================

def get_db_connection():
    """Establishes and returns a new database connection."""
    if not CONFIG_LOADED_SUCCESSFULLY:
        return None
    try:
        return mysql.connector.connect(host=DB_HOST, database=DB_DATABASE, user=DB_USER, password=DB_PASSWORD)
    except Error as e:
        logging.error(f"DB connection failed: {e}")
        st.error("Database connection failed. Please try again later.")
        return None

def close_db_connection(conn, cursor=None):
    """Safely closes a database cursor and connection."""
    if cursor:
        try: cursor.close()
        except Error: pass
    if conn and conn.is_connected():
        try: conn.close()
        except Error: pass

def get_user_details(user_email):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT first_name, last_name FROM user_registration WHERE Email_ID = %s", (user_email,))
            return cursor.fetchone()
    except Error as e:
        logging.error(f"Error fetching user details for {user_email}: {e}")
        return None
    finally:
        close_db_connection(conn)

def is_admin_of_an_organisation(admin_email):
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM admin_team_members WHERE admin_email = %s", (admin_email,))
            result = cursor.fetchone()
            return result.get('count', 0) > 0 if result else False
    except Error as e:
        logging.error(f"DB Error checking admin linkage for {admin_email}: {e}")
        return False
    finally:
        close_db_connection(conn)

def get_team_info_for_member(member_email, conn):
    """Finds a team member's admin and counts total members, using an existing connection."""
    try:
        with conn.cursor(dictionary=True, buffered=True) as cursor:
            cursor.execute("SELECT admin_email FROM admin_team_members WHERE team_member_email = %s LIMIT 1", (member_email,))
            result = cursor.fetchone()
            if not result: return None, 0

            admin_email = result['admin_email']
            cursor.execute("SELECT COUNT(*) as total_members FROM admin_team_members WHERE admin_email = %s", (admin_email,))
            count_result = cursor.fetchone()
            total_members = count_result['total_members'] if count_result else 0
            return admin_email, total_members
    except Error as e:
        logging.error(f"Error in get_team_info_for_member for {member_email}: {e}")
        return None, 0

def get_or_create_active_submission(user_email, TEAM_AVERAGE_DATA_WINDOW_DAYS):
    conn = get_db_connection()
    if not conn: return None
    try:
        with conn.cursor(dictionary=True, buffered=True) as cursor:
            query_latest = "SELECT submission_id, status, completion_time FROM Submissions WHERE Email_ID = %s ORDER BY start_time DESC LIMIT 1"
            cursor.execute(query_latest, (user_email,))
            latest_submission = cursor.fetchone()
            
            if latest_submission:
                if latest_submission['status'] == 'In Progress':
                    return {'submission_id': latest_submission['submission_id'], 'action': 'CONTINUE_IN_PROGRESS', 'message': 'Resuming your previous survey session.'}
                
                elif latest_submission['status'] == 'Completed' and latest_submission['completion_time'] and latest_submission['completion_time'] > (datetime.now() - timedelta(days=TEAM_AVERAGE_DATA_WINDOW_DAYS)):
                    admin_email, total_team_members = get_team_info_for_member(user_email, conn)
                    if not admin_email:
                        return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_THANKS_RECENT_COMPLETE_ATHLETE', 'message': 'Thank you for completing the survey!'}
                    
                    _, valid_completions_count = get_team_members_and_status(admin_email)
                    
                    if total_team_members > 0 and valid_completions_count >= total_team_members:
                        return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_DASHBOARD_RECENT_COMPLETE', 'message': 'Your entire team has completed the survey! The dashboard is now active.'}
                    else:
                        message = f'Thank you for completing the survey. The dashboard will unlock when all team members have completed it. ({valid_completions_count}/{total_team_members} complete)'
                        return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_WAITING_RECENT_COMPLETE_OTHER', 'message': message}

            insert_query = "INSERT INTO Submissions (Email_ID, start_time, status) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (user_email, datetime.now(), 'In Progress'))
            conn.commit()
            new_id = cursor.lastrowid
            return {'submission_id': new_id, 'action': 'START_NEW', 'message': 'Starting a new survey session.'}
    except Error as e:
        logging.error(f"Error managing submission for {user_email}: {e}")
        return None
    finally:
        close_db_connection(conn)

def load_user_progress(user_email, submission_id, survey_questions):
    responses = {cat: {q: "Select" for q in survey_questions[cat]} for cat in survey_questions}
    saved_categories = set()
    conn = get_db_connection()
    if not conn: return responses, saved_categories
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM Category_Completed WHERE submission_id = %s AND Email_ID = %s", (submission_id, user_email))
            completion_row = cursor.fetchone()
            if completion_row:
                for cat_key in survey_questions.keys():
                    if completion_row.get(cat_key) == 1:
                        saved_categories.add(cat_key)
    except Error as e:
        logging.error(f"MySQL Error loading progress for submission {submission_id}: {e}")
    finally:
        close_db_connection(conn)
    return responses, saved_categories

def update_submission_to_completed(submission_id):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            query = "UPDATE Submissions SET completion_time = %s, status = %s WHERE submission_id = %s"
            cursor.execute(query, (datetime.now(), 'Completed', submission_id))
            conn.commit()
    except Error as e:
        logging.error(f"MySQL Error updating submission {submission_id}: {e}")
    finally:
        close_db_connection(conn)

def save_category_to_db(cat_key, responses, user_email, submission_id):
    conn = get_db_connection()
    if not conn: return None
    avg_score = None
    try:
        with conn.cursor() as cursor:
            # ... (Full logic for calculating average and building SQL query)
            pass
    except Error as e:
        logging.error(f"MySQL Error saving category {cat_key}: {e}")
        conn.rollback()
        return None
    finally:
        close_db_connection(conn)
    return avg_score

def save_category_completion(cat_key, user_email, submission_id):
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            query = f"INSERT INTO Category_Completed (Email_ID, submission_id, `{cat_key}`) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE `{cat_key}` = 1"
            cursor.execute(query, (user_email, submission_id))
            conn.commit()
    except Error as e:
        logging.error(f"MySQL Error updating category completion for {cat_key}: {e}")
        conn.rollback()
    finally:
        close_db_connection(conn)

# ... other database functions like get_team_members_and_status can be included here ...

# ======================================================================================
# EMAIL HELPER FUNCTIONS
# ======================================================================================

def _send_email_generic_internal(recipient_email, subject, body_html, log_type="Generic"):
    if not all([SENDER_EMAIL, SENDER_APP_PASSWORD, SMTP_SERVER, SMTP_PORT]):
        logging.error(f"CRITICAL: Email misconfiguration for {log_type}. Secrets not fully loaded.")
        return False
    msg = MIMEText(body_html, 'html')
    msg['Subject'], msg['From'], msg['To'] = subject, SENDER_EMAIL, recipient_email
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, int(SMTP_PORT), timeout=10) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        logging.info(f"Successfully sent {log_type} email to {recipient_email}")
        return True
    except Exception as e:
        logging.error(f"ERROR sending {log_type} email to {recipient_email}: {e}")
        return False

def send_survey_completion_email(recipient_email, recipient_name):
    subject = "VClarifi Survey Completed - Thank You!"
    body = f"<html><body><p>Dear {recipient_name},</p><p>Thank you for completing the VClarifi survey!</p></body></html>"
    return _send_email_generic_internal(recipient_email, subject, body, "Survey Completion")

# ======================================================================================
# UI & STATE MANAGEMENT FUNCTIONS
# ======================================================================================

def initialize_survey_session(user_email, survey_questions, TEAM_AVERAGE_DATA_WINDOW_DAYS):
    submission_info = get_or_create_active_submission(user_email, TEAM_AVERAGE_DATA_WINDOW_DAYS)
    if not submission_info:
        st.error("Could not initialize your survey session. Please try again.")
        st.session_state.session_initialized = False
        return

    st.session_state.submission_id = submission_info.get('submission_id')
    st.session_state.survey_action = submission_info['action']
    st.session_state.survey_message = submission_info['message']
    st.session_state.is_admin = is_admin_of_an_organisation(user_email)
    
    if st.session_state.survey_action in ['CONTINUE_IN_PROGRESS', 'START_NEW']:
        responses, saved_cats = load_user_progress(user_email, st.session_state.submission_id, survey_questions)
        st.session_state.responses = responses
        st.session_state.saved_categories = saved_cats
    else:
        st.session_state.responses = {}
        st.session_state.saved_categories = set()
    
    st.session_state.session_initialized = True

def transition_to_finished_state(user_email, submission_id, TEAM_AVERAGE_DATA_WINDOW_DAYS):
    with st.spinner("Finalizing your survey..."):
        update_submission_to_completed(submission_id)
        user_details = get_user_details(user_email)
        user_name = f"{user_details['first_name']} {user_details['last_name']}" if user_details else user_email
        send_survey_completion_email(user_email, user_name)

        final_info = get_or_create_active_submission(user_email, TEAM_AVERAGE_DATA_WINDOW_DAYS)
        if final_info:
            st.session_state.survey_action = final_info['action']
            st.session_state.survey_message = final_info['message']
        
        st.session_state.selected_category = None
    st.rerun()

# ======================================================================================
# UI RENDERING FUNCTIONS
# ======================================================================================

def render_category_grid(survey_questions):
    st.title("QUESTIONNAIRE")
    st.subheader("Choose a category to begin or continue.")
    cols = st.columns(3)
    for i, cat_key in enumerate(survey_questions.keys()):
        is_completed = cat_key in st.session_state.get('saved_categories', set())
        with cols[i % 3]:
            if st.button(cat_key, key=f"btn_{cat_key}", use_container_width=True):
                st.session_state.selected_category = cat_key
                st.rerun()
            st.caption("✅ Completed" if is_completed else "⚪️ Pending")

def render_question_form(user_email, survey_questions, likert_options, TEAM_AVERAGE_DATA_WINDOW_DAYS):
    cat_key = st.session_state.selected_category
    st.subheader(f"Category: {cat_key}")
    st.markdown("---")
    questions = survey_questions[cat_key]
    answered_count = 0
    for q_key, q_text in questions.items():
        st.markdown(f"**{q_text}**")
        current_response = st.session_state.responses[cat_key].get(q_key, "Select")
        response_index = likert_options.index(current_response) if current_response in likert_options else 0
        selected_val = st.radio(label=q_key, options=likert_options, index=response_index, key=f"radio_{cat_key}_{q_key}", label_visibility="collapsed")
        st.session_state.responses[cat_key][q_key] = selected_val
        if selected_val != "Select": answered_count += 1
    st.markdown("---")
    if answered_count == len(questions):
        is_last_category = (len(st.session_state.saved_categories) == len(survey_questions) - 1) and (cat_key not in st.session_state.saved_categories)
        button_text = "Submit & Finish Survey" if is_last_category else "Save & Continue"
        if st.button(button_text, use_container_width=True, type="primary"):
            if save_category_to_db(cat_key, st.session_state.responses, user_email, st.session_state.submission_id) is not None:
                save_category_completion(cat_key, user_email, st.session_state.submission_id)
                st.session_state.saved_categories.add(cat_key)
                if len(st.session_state.saved_categories) == len(survey_questions):
                    transition_to_finished_state(user_email, st.session_state.submission_id, TEAM_AVERAGE_DATA_WINDOW_DAYS)
                else:
                    st.success(f"'{cat_key}' section saved!")
                    st.session_state.selected_category = None
                    st.rerun()
            else:
                st.error("Failed to save your progress. Please try again.")
    else:
        st.caption(f"Please answer all {len(questions) - answered_count} remaining questions to continue.")

def render_admin_panel(user_email, COMPLETED_SURVEY_ACTIONS):
    if not st.session_state.get('is_admin') or st.session_state.get('selected_category') is not None:
        return
    st.markdown("---")
    if st.session_state.get('survey_action') in COMPLETED_SURVEY_ACTIONS:
        with st.expander("👑 Admin Panel", expanded=False):
            st.info("Admin features are under development.")
    else:
        st.warning("🔒 **Admin Panel Locked**\n\nYou must complete your own survey to manage your team.")

def render_completed_view(navigate_to):
    if st.session_state.survey_action == 'VIEW_DASHBOARD_RECENT_COMPLETE':
        st.success("🎉 Your team has completed the survey! The dashboard is now available.")
        if st.button("View My Dashboard", use_container_width=True, type="primary"):
            navigate_to("Dashboard")

# ======================================================================================
# MAIN SURVEY APPLICATION
# ======================================================================================

def survey(navigate_to, user_email, **kwargs):
    """
    Main function to run the survey page, acting as a router for different UI states.
    """
    if not CONFIG_LOADED_SUCCESSFULLY:
        return

    # --- Constants and Definitions ---
    TEAM_AVERAGE_DATA_WINDOW_DAYS = 90
    COMPLETED_SURVEY_ACTIONS = {'VIEW_DASHBOARD_RECENT_COMPLETE', 'VIEW_WAITING_RECENT_COMPLETE_OTHER', 'VIEW_THANKS_RECENT_COMPLETE_ATHLETE'}
    likert_options = ["Select", "1: Not at all", "2: To a very little extent", "3: To a little extent", "4: To a moderate extent", "5: To a fairly large extent", "6: To a great extent", "7: To a very great extent"]
     # Survey questions categorized by themes
    survey_questions = {
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
    
    # --- Session Initialization ---
    if not st.session_state.get('session_initialized'):
        initialize_survey_session(user_email, survey_questions, TEAM_AVERAGE_DATA_WINDOW_DAYS)
        st.rerun()

    # --- Page Display ---
    st.info(st.session_state.get('survey_message', 'Welcome!'))
    
    # --- Main UI Router ---
    survey_action = st.session_state.get('survey_action')
    selected_category = st.session_state.get('selected_category')

    if survey_action in COMPLETED_SURVEY_ACTIONS:
        render_completed_view(navigate_to)
    elif selected_category:
        render_question_form(user_email, survey_questions, likert_options, TEAM_AVERAGE_DATA_WINDOW_DAYS)
    else:
        render_category_grid(survey_questions)

    render_admin_panel(user_email, COMPLETED_SURVEY_ACTIONS)
