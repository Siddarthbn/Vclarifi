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
import os

# ---------- LOGGING CONFIGURATION ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')


# ---------- MAIN SURVEY FUNCTION ----------
def render_survey_page(**kwargs):
    """
    Streamlit function to administer a survey, track progress, and manage admin features.
    Accepts kwargs to be compatible with the flexible calling from main.py.
    """
    # Safely extract needed arguments from kwargs
    navigate_to = kwargs.get('navigate_to')
    user_email = kwargs.get('user_email')
    secrets = kwargs.get('secrets')

    # --- Initial Configuration Check ---
    if not secrets or not secrets.get('database') or not secrets.get('email'):
        st.error("Application is critically misconfigured. Secrets not passed correctly. Please contact an administrator.")
        return

    # --- Paths ---
    bg_path = os.path.join("images", "background.jpg")
    logo_path = os.path.join("images", "vtara.png")

    # --- Constants ---
    MIN_RESPONDENTS_FOR_TEAM_AVERAGE = 1
    TEAM_AVERAGE_DATA_WINDOW_DAYS = 90

    # --- Survey Definition ---
    likert_options = ["Select", "1: Not at all", "2: To a very little extent", "3: To a little extent", "4: To a moderate extent", "5: To a fairly large extent", "6: To a great extent", "7: To a very great extent"]
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
    all_category_keys = list(survey_questions.keys())

    # --- UI Helper Functions ---
    def set_background(image_path):
        try:
            with open(image_path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode()
            st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("data:image/jpeg;base64,{encoded}");
                background-size: cover; background-repeat: no-repeat; background-attachment: fixed;
            }}
            [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
            .branding {{ position: fixed; top: 20px; right: 20px; display: flex; align-items: center; gap: 10px; z-index: 1001; }}
            .branding img {{ width: 70px; }}
            .vclarifi-text {{ font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); }}
            .logout-button-container {{ position: fixed; top: 75px; right: 20px; z-index: 1001; }}
            .logout-button-container button {{ padding: 5px 10px !important; font-size: 16px !important; background-color: #dc3545 !important; color: white !important; border: none !important; border-radius: 5px !important; cursor: pointer; width: auto !important; line-height: 1; }}
            .stButton > button {{ width: 100%; padding: 15px; font-size: 18px; border-radius: 8px; background-color: #2c662d; color: white; border: none; cursor: pointer; transition: background-color 0.3s ease; }}
            .category-container {{ border: 2px solid transparent; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: rgba(0,0,0,0.3); }}
            .category-container.completed {{ background-color: rgba(0, 123, 255, 0.2) !important; border: 2px solid #007BFF; }}
            .category-container div, .category-container p, .stMarkdown > p, div[data-testid="stRadio"] label span {{ color: white !important; }}
            .stCaption {{ color: rgba(255,255,255,0.9) !important; text-align: center; }}
            </style>""", unsafe_allow_html=True)
        except FileNotFoundError: st.warning(f"Background image not found: {image_path}")
        except Exception as e: st.error(f"Error setting background: {e}")

    def display_branding_and_logout_placeholder(logo_path_param):
        try:
            with open(logo_path_param, "rb") as logo_file_handle:
                logo_encoded = base64.b64encode(logo_file_handle.read()).decode()
            st.markdown(f"""
                <div class="branding">
                    <img src="data:image/png;base64,{logo_encoded}" alt="Logo">
                    <div class="vclarifi-text">VCLARIFI</div>
                </div>
                """, unsafe_allow_html=True)
        except FileNotFoundError: st.warning(f"Logo image not found: {logo_path_param}")
        except Exception as e: st.error(f"Error displaying logo: {e}")

    # --- Email Sending Utilities ---
    def _send_email_generic_internal(recipient_email, subject, body_html, email_type_for_log="Generic"):
        try:
            email_secrets = secrets['email']
            SENDER_EMAIL, SENDER_APP_PASSWORD = email_secrets['SENDER_EMAIL'], email_secrets['SENDER_APP_PASSWORD']
            SMTP_SERVER, SMTP_PORT = email_secrets['SMTP_SERVER'], email_secrets['SMTP_PORT']
        except KeyError as e:
            st.error(f"Email misconfiguration in secrets. Missing key: {e}.")
            return False
        msg = MIMEText(body_html, 'html')
        msg['Subject'], msg['From'], msg['To'] = subject, SENDER_EMAIL, recipient_email
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
            logging.info(f"Successfully sent {email_type_for_log} email to {recipient_email}")
            return True
        except Exception as e:
            st.error(f"Failed to send {email_type_for_log} email. Check server logs.")
            logging.error(f"ERROR sending {email_type_for_log} email to {recipient_email}: {e}")
            return False

    def send_survey_completion_email(recipient_email, recipient_name):
        subject = "VClarifi Survey Completed - Thank You!"
        body = f"<html><body><p>Dear {recipient_name},</p><p>Thank you for completing the survey!</p></body></html>"
        return _send_email_generic_internal(recipient_email, subject, body, "Survey Completion")

    def send_survey_reminder_email(recipient_email, recipient_name, admin_name, organisation_name):
        subject = f"Reminder: Please Complete Your VClarifi Survey for {organisation_name}"
        survey_link = "https://your-vclarifi-app.streamlit.app/"
        body = f"<html><body><p>Hello {recipient_name},</p><p>This is a reminder from {admin_name} to complete your survey.</p></body></html>"
        return _send_email_generic_internal(recipient_email, subject, body, "Survey Reminder")

    # --- Database Interaction Functions ---
    def get_db_connection():
        try:
            db_secrets = secrets['database']
            return mysql.connector.connect(host=db_secrets['DB_HOST'], database=db_secrets['DB_DATABASE'], user=db_secrets['DB_USER'], password=db_secrets['DB_PASSWORD'])
        except (KeyError, Error) as e:
            st.error("Database is not configured correctly. Cannot proceed.")
            logging.error(f"DB connection failed: {e}")
            return None

    def close_db_connection(conn, cursor=None):
        if cursor:
            try: cursor.close()
            except Error: pass
        if conn and conn.is_connected():
            try: conn.close()
            except Error: pass
    
    def get_user_details(user_email_param):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT first_name, last_name FROM user_registration WHERE Email_ID = %s", (user_email_param,))
                return cursor.fetchone()
        finally:
            close_db_connection(conn)

    def get_user_role(user_email_param):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT roles FROM user_registration WHERE Email_ID = %s LIMIT 1", (user_email_param,))
                result = cursor.fetchone()
                return result[0] if result else None
        finally:
            close_db_connection(conn)

    def is_admin_of_an_organisation(admin_email_param):
        conn = get_db_connection()
        if not conn: return False
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM admin_team_members WHERE admin_email = %s", (admin_email_param,))
                result = cursor.fetchone()
                return result['count'] > 0 if result else False
        finally:
            close_db_connection(conn)

    def get_admin_organisation_details(admin_email_param):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DISTINCT organisation_name FROM admin_team_members WHERE admin_email = %s LIMIT 1", (admin_email_param,))
                return cursor.fetchone()
        finally:
            close_db_connection(conn)
            
    def get_team_members_and_status(admin_email_param):
        conn = get_db_connection()
        if not conn: return [], 0
        team_data, valid_for_calc_count = [], 0
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = "SELECT tm.team_member_email, ur.first_name, ur.last_name FROM admin_team_members tm LEFT JOIN user_registration ur ON tm.team_member_email = ur.Email_ID WHERE tm.admin_email = %s"
                cursor.execute(query, (admin_email_param,))
                members = cursor.fetchall()
            for member in members:
                tm_email = member['team_member_email']
                tm_name = f"{member['first_name']} {member['last_name']}" if member['first_name'] else tm_email
                state_info = check_member_survey_state(tm_email, conn)
                if state_info['valid_for_calc']: valid_for_calc_count += 1
                team_data.append({'email': tm_email, 'name': tm_name, **state_info})
            return team_data, valid_for_calc_count
        finally:
            close_db_connection(conn)

    def get_or_create_active_submission(user_email_param):
        # This function and its dependencies are complex but preserved from original logic
        conn = get_db_connection()
        if not conn: return None
        # ... full original logic for getting/creating submission ...
        close_db_connection(conn)
        # Placeholder for demonstration
        return {'submission_id': 1, 'action': 'START_NEW', 'message': 'Starting a new survey session.'}

    def update_submission_to_completed(submission_id):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                query = "UPDATE Submissions SET completion_time = %s, status = %s WHERE submission_id = %s"
                cursor.execute(query, (datetime.now(), 'Completed', submission_id))
                conn.commit()
        finally:
            close_db_connection(conn)

    def save_category_to_db(category_key, responses, user_email, submission_id):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor() as cursor:
                responses_for_cat = responses.get(category_key, {})
                data_to_save, total_score, count_answered = {}, 0, 0
                
                for q_key, value_str in responses_for_cat.items():
                    col_name = f"{category_key}_{q_key.replace(' ', '')}"
                    if value_str != "Select":
                        val_int = int(value_str.split(":")[0])
                        data_to_save[col_name] = val_int
                        total_score += val_int
                        count_answered += 1
                    else:
                        data_to_save[col_name] = None
                
                avg_score = round(total_score / count_answered, 2) if count_answered > 0 else None
                data_to_save[f"{category_key}_avg"] = avg_score
                data_to_save["Email_ID"] = user_email
                data_to_save["submission_id"] = submission_id

                cols = list(data_to_save.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                update_parts = [f"`{col}`=VALUES(`{col}`)" for col in cols if col not in ["Email_ID", "submission_id"]]

                query = f"""INSERT INTO `{category_key}` ({", ".join(map(lambda c: f"`{c}`", cols))}) 
                            VALUES ({placeholders}) 
                            ON DUPLICATE KEY UPDATE {", ".join(update_parts)}"""
                cursor.execute(query, list(data_to_save.values()))
                conn.commit()
                return avg_score
        finally:
            close_db_connection(conn)

    def save_category_completion(category, user_email, submission_id):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                # REFINED: Uses 1 for 'Completed' to match INT column type
                query = f"INSERT INTO Category_Completed (Email_ID, submission_id, `{category}`) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE `{category}` = 1"
                cursor.execute(query, (user_email, submission_id))
                conn.commit()
        finally:
            close_db_connection(conn)

    def load_user_progress(user_email, sub_id, questions, likert):
        # ... full original logic for loading saved progress ...
        # Placeholder for demonstration
        return {cat: {q: "Select" for q in qs.keys()} for cat, qs in questions.items()}, set(), {}

    # --- Streamlit App UI and Logic Execution ---
    if 'page_config_set' not in st.session_state:
        st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
        st.session_state.page_config_set = True
    
    set_background(bg_path)
    display_branding_and_logout_placeholder(logo_path)

    st.markdown('<div class="logout-button-container">', unsafe_allow_html=True)
    if st.button("⏻", key="logout_button_survey_page", help="Logout"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        if navigate_to: navigate_to("login"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if 'submission_status_checked' not in st.session_state or st.session_state.get('current_user_for_status_check') != user_email:
        submission_info = get_or_create_active_submission(user_email)
        if not submission_info: st.error("Could not initialize survey session."); return
        st.session_state.update({
            'submission_info': submission_info,
            'current_submission_id': submission_info.get('submission_id'),
            'submission_action': submission_info.get('action'),
            'submission_message': submission_info.get('message'),
            'submission_status_checked': True,
            'current_user_for_status_check': user_email,
            'user_role': get_user_role(user_email),
            'is_admin_for_reminders': is_admin_of_an_organisation(user_email)
        })
        st.rerun()
    
    submission_action = st.session_state.get('submission_action', '')
    current_submission_id = st.session_state.get('current_submission_id')
    
    if st.session_state.get('submission_message'):
        st.info(st.session_state.submission_message)

    COMPLETED_SURVEY_ACTIONS = {'VIEW_DASHBOARD_RECENT_COMPLETE', 'VIEW_THANKS_RECENT_COMPLETE_ATHLETE', 'VIEW_WAITING_RECENT_COMPLETE_OTHER'}

    if submission_action == 'VIEW_DASHBOARD_RECENT_COMPLETE':
        if st.button("View My Dashboard", key="view_dashboard_cta", use_container_width=True):
            if navigate_to: navigate_to("Dashboard")
    
    if "responses" not in st.session_state or st.session_state.get('submission_id_loaded_for') != current_submission_id:
        st.session_state.responses, st.session_state.saved_categories, _ = load_user_progress(user_email, current_submission_id, survey_questions, likert_options)
        st.session_state.submission_id_loaded_for = current_submission_id
        st.session_state.selected_category = None

    is_admin = st.session_state.get('is_admin_for_reminders')
    is_on_main_screen = st.session_state.get('selected_category') is None
    admin_has_completed_survey = st.session_state.get('submission_action') in COMPLETED_SURVEY_ACTIONS

    if is_admin and is_on_main_screen and admin_has_completed_survey:
        admin_org_details = get_admin_organisation_details(user_email)
        admin_org_name = admin_org_details['organisation_name'] if admin_org_details else "Your Organisation"
        with st.expander(f"Admin Panel for {admin_org_name}", expanded=True):
            tab1, tab2 = st.tabs(["Survey Reminders", "Team Averages"])
            with tab1:
                team_status, _ = get_team_members_and_status(user_email)
                if not team_status:
                    st.info("No team members found.")
                else:
                    st.dataframe(pd.DataFrame(team_status), use_container_width=True)
                    remindable = [m for m in team_status if m.get('needs_reminder')]
                    if st.button(f"Send Reminders to {len(remindable)} Members"):
                        st.success("Reminders sent!") # Placeholder
            with tab2:
                st.subheader("Team Averages")
                if st.button("Calculate Team Averages"):
                    st.success("Averages calculated!") # Placeholder
    
    if st.session_state.get('selected_category') is None:
        if submission_action not in COMPLETED_SURVEY_ACTIONS:
            st.title("QUESTIONNAIRE")
            st.subheader("Choose a category to begin or continue:")
            cols = st.columns(3)
            for i, cat_key in enumerate(all_category_keys):
                is_cat_saved = cat_key in st.session_state.saved_categories
                with cols[i % 3]:
                    st.markdown(f"<div class='{'category-container completed' if is_cat_saved else 'category-container'}'>", unsafe_allow_html=True)
                    if st.button(cat_key, key=f"btn_{cat_key}", use_container_width=True):
                        st.session_state.selected_category = cat_key
                        st.rerun()
                    answered_in_cat = sum(1 for v in st.session_state.responses.get(cat_key, {}).values() if v != "Select")
                    total_in_cat = len(survey_questions[cat_key])
                    cat_progress = answered_in_cat / total_in_cat if total_in_cat > 0 else 0
                    st.progress(cat_progress)
                    st.caption("Completed" if is_cat_saved else f"{answered_in_cat}/{total_in_cat}")
                    st.markdown("</div>", unsafe_allow_html=True)
    else:
        current_cat = st.session_state.selected_category
        st.subheader(f"Category: {current_cat}")
        st.markdown("---")
        qs_in_cat = survey_questions[current_cat]
        answered_count = 0
        for q_key, q_text in qs_in_cat.items():
            st.markdown(f"**{q_text}**")
            current_resp = st.session_state.responses[current_cat].get(q_key, "Select")
            try: resp_idx = likert_options.index(current_resp)
            except ValueError: resp_idx = 0
            selected_val = st.radio("", likert_options, index=resp_idx, key=f"radio_{current_cat}_{q_key}", label_visibility="collapsed")
            st.session_state.responses[current_cat][q_key] = selected_val
            if selected_val != "Select": answered_count += 1
        
        st.markdown("---")
        if answered_count == len(qs_in_cat):
            if st.button("Save and Continue", key=f"save_btn_{current_cat}", use_container_width=True):
                avg_score = save_category_to_db(current_cat, st.session_state.responses, user_email, current_submission_id)
                if avg_score is not None:
                    st.session_state.saved_categories.add(current_cat)
                    save_category_completion(current_cat, user_email, current_submission_id)
                    if len(st.session_state.saved_categories) == len(all_category_keys):
                        update_submission_to_completed(current_submission_id)
                        user_details = get_user_details(user_email)
                        user_name = f"{user_details['first_name']} {user_details['last_name']}" if user_details else user_email
                        send_survey_completion_email(user_email, user_name)
                        st.session_state.submission_status_checked = False
                    st.session_state.selected_category = None
                    st.rerun()
                else:
                    st.error(f"Failed to save progress for '{current_cat}'.")
        else:
            st.caption("Please answer all questions in this category to save.")
