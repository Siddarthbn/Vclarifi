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

# ---------- LOGGING CONFIGURATION ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# ---------- AWS SECRETS MANAGER INTEGRATION ----------
@st.cache_data(ttl=600)  # Cache secrets for 10 minutes to reduce API calls
def get_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.

    This function is designed for secrets stored as key-value pairs, which the AWS API
    returns as a single JSON string. It includes robust error handling.
    """
    secret_name = "production/vclarifi/secrets"  # Your secret's unique name/path
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret_string = get_secret_value_response['SecretString']
        logging.info("Secrets Loaded Successfully from AWS.")
        return json.loads(secret_string)
    except Exception as e:
        # Log the full error for debugging but show a user-friendly message
        logging.error(f"AWS Secrets Manager Error: {e}")
        st.error("FATAL: Could not retrieve application secrets from AWS.")
        st.error("Please contact support and check IAM permissions and secret name.")
        return None

# ---------- GLOBAL CONFIGURATION (ROBUST STARTUP) ----------
# This block loads secrets from AWS into global variables. If it fails,
# it sets them to None and logs an error, preventing a crash on startup.
try:
    aws_secrets = get_aws_secrets()
    if aws_secrets:
        # --- REFINED LOGIC TO READ FROM A FLAT KEY/VALUE STRUCTURE ---
        # Database Configuration
        DB_HOST = aws_secrets.get('DB_HOST')
        DB_DATABASE = aws_secrets.get('DB_DATABASE')
        DB_USER = aws_secrets.get('DB_USER')
        DB_PASSWORD = aws_secrets.get('DB_PASSWORD')

        # Email Configuration
        SENDER_EMAIL = aws_secrets.get('SENDER_EMAIL')
        SENDER_APP_PASSWORD = aws_secrets.get('SENDER_APP_PASSWORD')
        SMTP_SERVER = aws_secrets.get('SMTP_SERVER')
        SMTP_PORT = aws_secrets.get('SMTP_PORT')

        # Check if all essential secrets were loaded
        if all([DB_HOST, DB_DATABASE, DB_USER, DB_PASSWORD, SENDER_EMAIL, SENDER_APP_PASSWORD, SMTP_SERVER, SMTP_PORT]):
            CONFIG_LOADED_SUCCESSFULLY = True
            logging.info("Configuration secrets loaded successfully from AWS (flat structure).")
        else:
            CONFIG_LOADED_SUCCESSFULLY = False
            logging.critical("FATAL: One or more essential secrets are missing from the AWS payload. Check keys like DB_HOST, SENDER_EMAIL, etc.")
            # Set all to None for consistency if any are missing
            DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
            SENDER_EMAIL = SENDER_APP_PASSWORD = SMTP_SERVER = SMTP_PORT = None
    else:
        # get_aws_secrets() returned None and already logged the error
        CONFIG_LOADED_SUCCESSFULLY = False
        DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
        SENDER_EMAIL = SENDER_APP_PASSWORD = SMTP_SERVER = SMTP_PORT = None

except Exception as e:
    logging.critical(f"FATAL: An unexpected error occurred during secrets processing. Error: {e}")
    # Set config variables to None so the app can still load without a NameError.
    DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
    SENDER_EMAIL = SENDER_APP_PASSWORD = SMTP_SERVER = SMTP_PORT = None
    CONFIG_LOADED_SUCCESSFULLY = False


# ---------- MAIN SURVEY FUNCTION ----------
def survey(navigate_to, user_email, **kwargs):
    """
    Streamlit function to administer a multi-category survey, save responses,
    track progress, and manage admin features.
    """
    # --- Initial Configuration Check ---
    if not CONFIG_LOADED_SUCCESSFULLY:
        st.error("Application is critically misconfigured. Cannot initialize survey. Please contact an administrator.")
        return

    # --- Paths ---
    # TODO: Update these paths to be correct for your environment
    bg_path = "images/background.jpg"
    logo_path = "images/vtara.png"

    # --- Constants ---
    MIN_RESPONDENTS_FOR_TEAM_AVERAGE = 1
    TEAM_AVERAGE_DATA_WINDOW_DAYS = 90 # Defines what counts as a "recent" survey

    # --- UI Helper Functions ---
    def set_background(image_path):
        """Sets the app background to cover the entire screen."""
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
        except FileNotFoundError: st.warning(f"Background image not found: {image_path}")
        except Exception as e: st.error(f"Error setting background: {e}")

    def display_branding_and_logout_placeholder(logo_path_param):
        """Displays the branding logo."""
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
        """Internal function to send emails using global config variables."""
        if not SENDER_EMAIL or not SENDER_APP_PASSWORD:
            st.error(f"Email misconfiguration for {email_type_for_log}. Contact admin.")
            logging.error(f"CRITICAL: Email sending misconfiguration for {email_type_for_log}. Secrets not loaded.")
            return False
        msg = MIMEText(body_html, 'html')
        msg['Subject'] = subject; msg['From'] = SENDER_EMAIL; msg['To'] = recipient_email
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, int(SMTP_PORT), timeout=10) as server:
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
        body = f"<html><body><p>Dear {recipient_name},</p><p>Thank you for successfully completing the VClarifi survey! Your responses have been recorded.</p><p>Your input is valuable to us.</p><p>Best regards,<br>The VClarifi Team</p></body></html>"
        return _send_email_generic_internal(recipient_email, subject, body, "Survey Completion")

    def send_survey_reminder_email(recipient_email, recipient_name, admin_name, organisation_name):
        subject = f"Reminder: Please Complete Your VClarifi Survey for {organisation_name}"
        survey_link = "https://your-vclarifi-app.streamlit.app/" # IMPORTANT: Update this URL
        body = f"<html><body><p>Hello {recipient_name},</p><p>This is a friendly reminder from {admin_name} of {organisation_name} to please complete your VClarifi survey.</p><p>Your participation is important for our collective insights.</p><p>Please use the following link to access the survey: <a href='{survey_link}'>{survey_link}</a></p><p>If you have already completed the survey recently, please disregard this message.</p><p>Thank you,<br>The VClarifi Team</p></body></html>"
        return _send_email_generic_internal(recipient_email, subject, body, "Survey Reminder")

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


    # --- Database Interaction Functions ---
    def get_db_connection():
        """Establishes and returns a database connection using global config variables."""
        if not DB_HOST:
            logging.error("DB connection attempt failed because secrets were not loaded.")
            st.error("Database is not configured. Cannot proceed.")
            return None
        try:
            return mysql.connector.connect(host=DB_HOST, database=DB_DATABASE, user=DB_USER, password=DB_PASSWORD)
        except Error as e:
            st.error(f"DB connection failed: {e}")
            logging.error(f"DB connection failed: {e}")
            return None

    def close_db_connection(conn, cursor=None):
        """Safely closes a database cursor and connection."""
        if cursor:
            try: cursor.close()
            except Error: pass
        if conn and conn.is_connected():
            try: conn.close()
            except Error: pass
    
    def get_user_details(user_email_param):
        conn = get_db_connection();
        if not conn: return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT first_name, last_name FROM user_registration WHERE Email_ID = %s", (user_email_param,))
                return cursor.fetchone()
        except Error as e: st.error(f"Error fetching user details for {user_email_param}: {e}"); return None
        finally: close_db_connection(conn)

    def get_user_role(user_email_param):
        conn = get_db_connection();
        if not conn: return None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT roles FROM user_registration WHERE Email_ID = %s LIMIT 1", (user_email_param,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Error as e: st.error(f"MySQL Error fetching user role: {e}"); return None
        finally: close_db_connection(conn)

    def is_admin_of_an_organisation(admin_email_param):
        conn = get_db_connection();
        if not conn: return False
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM admin_team_members WHERE admin_email = %s", (admin_email_param,))
                result = cursor.fetchone()
                return result['count'] > 0 if result else False
        except Error as e: logging.error(f"DB Error checking admin_team_members linkage: {e}"); return False
        finally: close_db_connection(conn)

    def get_admin_organisation_details(admin_email_param):
        conn = get_db_connection();
        if not conn: return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DISTINCT organisation_name FROM admin_team_members WHERE admin_email = %s LIMIT 1", (admin_email_param,))
                return cursor.fetchone()
        except Error as e: st.error(f"Error fetching admin organisation: {e}"); return None
        finally: close_db_connection(conn)

    def get_team_info_for_member(member_email, conn_param):
        """
        Finds a team member's admin and counts the total members on that team.
        Returns: tuple: (admin_email, total_team_members) or (None, 0) if not found.
        """
        try:
            with conn_param.cursor(dictionary=True, buffered=True) as cursor:
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

    def get_or_create_active_submission(user_email_param):
        """
        Determines the user's survey state. Activates dashboard only when the user's entire team is complete.
        """
        conn = get_db_connection();
        if not conn: return None
        try:
            with conn.cursor(dictionary=True, buffered=True) as cursor:
                query_latest = "SELECT submission_id, start_time, completion_time, status FROM Submissions WHERE Email_ID = %s ORDER BY start_time DESC LIMIT 1"
                cursor.execute(query_latest, (user_email_param,))
                latest_submission = cursor.fetchone()
                three_months_ago = datetime.now() - timedelta(days=TEAM_AVERAGE_DATA_WINDOW_DAYS)

                if latest_submission:
                    if latest_submission['status'] == 'In Progress':
                        return {'submission_id': latest_submission['submission_id'], 'action': 'CONTINUE_IN_PROGRESS', 'message': 'Resuming your previous survey session.'}
                    
                    elif latest_submission['status'] == 'Completed':
                        if latest_submission['completion_time'] and latest_submission['completion_time'] > three_months_ago:
                            user_role_local = get_user_role(user_email_param)
                            
                            if user_role_local == 'athlete':
                                return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_THANKS_RECENT_COMPLETE_ATHLETE', 'message': 'You have completed the survey.'}
                            
                            admin_email, total_team_members = get_team_info_for_member(user_email_param, conn)
                            
                            if not admin_email:
                                return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_THANKS_RECENT_COMPLETE_ATHLETE', 'message': 'Thank you for completing the survey!'}

                            _, valid_completions_count = get_team_members_and_status(admin_email)
                            
                            if total_team_members > 0 and valid_completions_count >= total_team_members:
                                return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_DASHBOARD_RECENT_COMPLETE', 'message': 'Your entire team has completed the survey! The dashboard is now active.'}
                            else:
                                message = f'Thank you for completing the survey. The dashboard will unlock when all team members have completed it. ({valid_completions_count}/{total_team_members} complete)'
                                return {'submission_id': latest_submission['submission_id'], 'action': 'VIEW_WAITING_RECENT_COMPLETE_OTHER', 'message': message}

                insert_query = "INSERT INTO Submissions (Email_ID, start_time, status) VALUES (%s, %s, %s)"
                cursor.execute(insert_query, (user_email_param, datetime.now(), 'In Progress'))
                conn.commit()
                new_submission_id = cursor.lastrowid
                return {'submission_id': new_submission_id, 'action': 'START_NEW', 'message': 'Starting a new survey session.'}
        except Error as e: st.error(f"MySQL Error managing submission: {e}"); return None
        finally: close_db_connection(conn)

    def update_submission_to_completed(submission_id_param):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                query = "UPDATE Submissions SET completion_time = %s, status = %s WHERE submission_id = %s"
                cursor.execute(query, (datetime.now(), 'Completed', submission_id_param)); conn.commit()
        except Error as e: st.error(f"MySQL Error updating submission to completed: {e}")
        finally: close_db_connection(conn)

    def save_category_to_db(category_key, responses_data, current_user_email, submission_id_param):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor() as cursor:
                current_category_responses = responses_data.get(category_key, {})
                if not current_category_responses: st.error(f"No responses for '{category_key}'."); return None
                total_score, count_answered = 0, 0; data_to_save = {}
                for q_key, value_str in current_category_responses.items():
                    col_name = f"{category_key}_{q_key.replace(' ', '').replace('-', '').replace('.', '')}"
                    if value_str != "Select":
                        try: val_int = int(value_str.split(":")[0]); data_to_save[col_name] = val_int; total_score += val_int; count_answered += 1
                        except (ValueError, IndexError): data_to_save[col_name] = None
                    else: data_to_save[col_name] = None
                avg_score = round(total_score / count_answered, 2) if count_answered > 0 else None
                data_to_save[f"{category_key}_avg"] = avg_score; data_to_save["Email_ID"] = current_user_email; data_to_save["submission_id"] = submission_id_param
                cols = list(data_to_save.keys()); cols_str = ", ".join([f"`{c}`" for c in cols]); placeholders = ", ".join(["%s"] * len(cols))
                update_values_parts = [f"`{col}` = VALUES(`{col}`)" for col in data_to_save if col not in ["Email_ID", "submission_id"]]
                if not update_values_parts: st.warning(f"No columns to update for {category_key}."); return None
                query = f"INSERT INTO `{category_key}` ({cols_str}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {', '.join(update_values_parts)}"
                cursor.execute(query, list(data_to_save.values())); conn.commit()
                return avg_score
        except Error as e: st.error(f"MySQL Error saving {category_key}: {e}"); conn.rollback(); return None
        finally: close_db_connection(conn)

    def save_averages_to_db(avg_dict_data, current_user_email, submission_id_param):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                data_to_save = {k: v for k, v in avg_dict_data.items() if v is not None}
                if not data_to_save: return
                data_to_save["Email_ID"] = current_user_email; data_to_save["submission_id"] = submission_id_param
                cols = list(data_to_save.keys()); cols_str = ", ".join([f"`{c}`" for c in cols]); placeholders = ", ".join(["%s"] * len(cols))
                update_values_parts = [f"`{k}` = VALUES(`{k}`)" for k in data_to_save if k not in ["Email_ID", "submission_id"]]
                if not update_values_parts: return
                query = f"INSERT INTO Averages ({cols_str}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {', '.join(update_values_parts)}"
                cursor.execute(query, list(data_to_save.values())); conn.commit()
        except Error as e: st.error(f"MySQL Error saving averages: {e}"); conn.rollback()
        finally: close_db_connection(conn)

    def save_category_completion(category_to_mark_completed, current_user_email, submission_id_param):
        conn = get_db_connection()
        if not category_to_mark_completed or not conn: return
        try:
            with conn.cursor() as cursor:
                col_name = f"`{category_to_mark_completed}`"
                query = f"INSERT INTO Category_Completed (Email_ID, submission_id, {col_name}) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE {col_name} = VALUES({col_name})"
                cursor.execute(query, (current_user_email, submission_id_param, 'Completed')); conn.commit()
        except Error as e: st.error(f"MySQL Error updating category completion for {category_to_mark_completed}: {e}"); conn.rollback()
        finally: close_db_connection(conn)

    def load_user_progress(current_user_email, submission_id_param, question_definitions_map, likert_options_list):
        loaded_responses = {cat_k: {q_k: "Select" for q_k in q_defs.keys()} for cat_k, q_defs in question_definitions_map.items()}
        loaded_saved_categories = set(); loaded_category_avgs = {}
        if not submission_id_param: return loaded_responses, loaded_saved_categories, loaded_category_avgs
        conn = get_db_connection()
        if not conn: return loaded_responses, loaded_saved_categories, loaded_category_avgs
        try:
            with conn.cursor(dictionary=True, buffered=True) as cursor:
                cursor.execute("SELECT * FROM Category_Completed WHERE Email_ID = %s AND submission_id = %s", (current_user_email, submission_id_param))
                completion_data_row = cursor.fetchone()
                if completion_data_row:
                    for cat_k_iter in question_definitions_map.keys():
                        if completion_data_row.get(cat_k_iter) == 'Completed': loaded_saved_categories.add(cat_k_iter)
                for cat_k_iter, q_defs_iter in question_definitions_map.items():
                    try:
                        cursor.execute(f"SELECT * FROM `{cat_k_iter}` WHERE Email_ID = %s AND submission_id = %s", (current_user_email, submission_id_param))
                        cat_responses_row = cursor.fetchone()
                        if cat_responses_row:
                            for q_k_iter in q_defs_iter.keys():
                                db_col_name = f"{cat_k_iter}_{q_k_iter.replace(' ', '').replace('-', '').replace('.', '')}"
                                if db_col_name in cat_responses_row and cat_responses_row[db_col_name] is not None:
                                    numeric_val = cat_responses_row[db_col_name]
                                    for option_item in likert_options_list:
                                        if option_item.startswith(str(numeric_val) + ":"): loaded_responses[cat_k_iter][q_k_iter] = option_item; break
                    except mysql.connector.errors.ProgrammingError as e_prog:
                        if "Table" in str(e_prog) and "doesn't exist" in str(e_prog): pass
                        else: st.error(f"DB ProgrammingError for {cat_k_iter}: {e_prog}");
                cursor.execute("SELECT * FROM Averages WHERE Email_ID = %s AND submission_id = %s", (current_user_email, submission_id_param))
                avg_data_row = cursor.fetchone()
                if avg_data_row:
                    for cat_k_iter in question_definitions_map.keys():
                        avg_col_name_iter = f"{cat_k_iter}_avg"
                        if avg_col_name_iter in avg_data_row and avg_data_row[avg_col_name_iter] is not None:
                            loaded_category_avgs[avg_col_name_iter] = float(avg_data_row[avg_col_name_iter])
        except Error as e: st.error(f"MySQL Error loading progress for {submission_id_param}: {e}")
        finally: close_db_connection(conn)
        return loaded_responses, loaded_saved_categories, loaded_category_avgs

    def check_member_survey_state(member_email_param, conn_param):
        try:
            with conn_param.cursor(dictionary=True, buffered=True) as cursor:
                query_latest_submission = "SELECT submission_id, status, completion_time FROM Submissions WHERE Email_ID = %s ORDER BY start_time DESC LIMIT 1"
                cursor.execute(query_latest_submission, (member_email_param,))
                latest_submission_details = cursor.fetchone()
                three_months_ago = datetime.now() - timedelta(days=TEAM_AVERAGE_DATA_WINDOW_DAYS)
                if not latest_submission_details: return {'display': 'Not Started', 'needs_reminder': True, 'valid_for_calc': False}
                current_submission_id = latest_submission_details['submission_id']
                submission_status_overall = latest_submission_details['status']
                submission_completion_time = latest_submission_details['completion_time']
                cursor.execute("SELECT * FROM Category_Completed WHERE submission_id = %s AND Email_ID = %s", (current_submission_id, member_email_param))
                cat_completed_row = cursor.fetchone()
                num_categories_done_in_record = 0
                all_categories_marked_in_record = False
                if cat_completed_row:
                    categories_done_list = [cat_col for cat_col in all_category_keys if cat_completed_row.get(cat_col) == 'Completed']
                    num_categories_done_in_record = len(categories_done_list)
                    if num_categories_done_in_record == len(all_category_keys): all_categories_marked_in_record = True
                is_valid_for_calc = (submission_status_overall == 'Completed' and all_categories_marked_in_record and submission_completion_time and submission_completion_time > three_months_ago)
                if submission_status_overall == 'In Progress':
                    return {'display': f'In Progress ({num_categories_done_in_record}/{len(all_category_keys)} cats)', 'needs_reminder': True, 'valid_for_calc': False}
                if submission_status_overall == 'Completed':
                    if is_valid_for_calc: return {'display': f"Completed ({submission_completion_time.strftime('%Y-%m-%d')})", 'needs_reminder': False, 'valid_for_calc': True}
                    else:
                        status_text = f"Completed (Old: {submission_completion_time.strftime('%Y-%m-%d')})" if submission_completion_time else "Completed (Legacy)"
                        return {'display': status_text, 'needs_reminder': True, 'valid_for_calc': False}
                return {'display': f'Status: {submission_status_overall}', 'needs_reminder': True, 'valid_for_calc': False}
        except Error as e: logging.error(f"Error checking member survey state for {member_email_param}: {e}"); return {'display': 'Error checking status', 'needs_reminder': False, 'valid_for_calc': False}

    def get_team_members_and_status(admin_email_param):
        team_data = []; conn = get_db_connection();
        if not conn: return team_data, 0
        valid_for_calc_count = 0
        try:
            with conn.cursor(dictionary=True) as cursor:
                query_team = "SELECT tm.team_member_email, ur.first_name, ur.last_name FROM admin_team_members tm LEFT JOIN user_registration ur ON tm.team_member_email = ur.Email_ID WHERE tm.admin_email = %s"
                cursor.execute(query_team, (admin_email_param,))
                members = cursor.fetchall()
            if not members: return team_data, 0
            for member in members:
                tm_email = member['team_member_email']
                tm_name = f"{member['first_name']} {member['last_name']}" if member['first_name'] else tm_email
                state_info = check_member_survey_state(tm_email, conn)
                if state_info['valid_for_calc']: valid_for_calc_count += 1
                team_data.append({'email': tm_email, 'name': tm_name, 'status_display': state_info['display'], 'needs_reminder': state_info['needs_reminder'], 'valid_for_calc': state_info['valid_for_calc']})
            return team_data, valid_for_calc_count
        except Error as e: st.error(f"Error fetching team members & status: {e}"); return [], 0
        finally: close_db_connection(conn)

    def create_team_overall_averages_table(conn):
        try:
            with conn.cursor() as cursor:
                cursor.execute("""CREATE TABLE IF NOT EXISTS Team_Overall_Averages (id INT AUTO_INCREMENT PRIMARY KEY, organisation_name VARCHAR(255) NOT NULL, admin_email VARCHAR(255), reporting_period_identifier VARCHAR(255) NOT NULL, Leadership_team_avg DECIMAL(3,2), Empower_team_avg DECIMAL(3,2), Sustainability_team_avg DECIMAL(3,2), CulturePulse_team_avg DECIMAL(3,2), Bonding_team_avg DECIMAL(3,2), Influencers_team_avg DECIMAL(3,2), number_of_respondents INT, calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, UNIQUE KEY unique_org_period (organisation_name, reporting_period_identifier))""")
                conn.commit()
        except Error as e: st.error(f"Error creating Team_Overall_Averages table: {e}")

    def get_valid_completed_submission_id_for_member(member_email, days_window, all_category_keys_list, conn_param):
        try:
            with conn_param.cursor(dictionary=True, buffered=True) as cursor:
                date_threshold = datetime.now() - timedelta(days=days_window)
                query_submission = "SELECT submission_id FROM Submissions WHERE Email_ID = %s AND status = 'Completed' AND completion_time >= %s ORDER BY completion_time DESC LIMIT 1"
                cursor.execute(query_submission, (member_email, date_threshold))
                submission = cursor.fetchone()
                if not submission: return None
                sub_id = submission['submission_id']
                cursor.execute("SELECT * FROM Category_Completed WHERE submission_id = %s", (sub_id,))
                cat_completion_row = cursor.fetchone()
                if not cat_completion_row: return None
                completed_count = sum(1 for cat_key in all_category_keys_list if cat_completion_row.get(cat_key) == 'Completed')
                return sub_id if completed_count == len(all_category_keys_list) else None
        except Error as e: logging.error(f"Error in get_valid_submission_id for {member_email}: {e}"); return None

    def get_individual_averages_for_submission(submission_id, conn_param):
        try:
            with conn_param.cursor(dictionary=True) as cursor:
                avg_cols_to_select = [f"`{cat_key}_avg`" for cat_key in all_category_keys]
                query = f"SELECT {', '.join(avg_cols_to_select)} FROM Averages WHERE submission_id = %s"
                cursor.execute(query, (submission_id,))
                return cursor.fetchone()
        except Error as e: logging.error(f"Error in get_individual_averages for {submission_id}: {e}"); return None
        
    def save_team_overall_averages_to_db(org_name, admin_email_val, reporting_id, team_avg_data, num_respondents, conn_param):
        try:
            with conn_param.cursor() as cursor:
                data_for_insert = {'organisation_name': org_name, 'admin_email': admin_email_val, 'reporting_period_identifier': reporting_id, 'number_of_respondents': num_respondents}
                for cat_key in all_category_keys: data_for_insert[f'{cat_key}_team_avg'] = team_avg_data.get(f'{cat_key}_avg')
                cols = list(data_for_insert.keys()); placeholders = ", ".join(["%s"] * len(cols))
                update_assignments = [f"`{col}` = VALUES(`{col}`)" for col in cols if col not in ['organisation_name', 'reporting_period_identifier']]
                sql_query = f"INSERT INTO Team_Overall_Averages ({', '.join(f'`{c}`' for c in cols)}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {', '.join(update_assignments)}"
                cursor.execute(sql_query, list(data_for_insert.values())); conn_param.commit()
                return True
        except Error as e: st.error(f"Error saving team averages: {e}"); conn_param.rollback(); return False

    def get_latest_team_overall_averages(org_name, reporting_id, conn_param):
        try:
            with conn_param.cursor(dictionary=True) as cursor:
                query = "SELECT * FROM Team_Overall_Averages WHERE organisation_name = %s AND reporting_period_identifier = %s ORDER BY calculation_date DESC LIMIT 1"
                cursor.execute(query, (org_name, reporting_id))
                return cursor.fetchone()
        except Error as e: logging.error(f"Error fetching latest team averages for {org_name}: {e}"); return None

    def handle_calculate_team_averages(admin_email_param, admin_org_name_param):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (admin_email_param,))
                team_members_rows = cursor.fetchall()
            if not team_members_rows: st.info(f"No team members found for {admin_org_name_param}."); return
            valid_individual_averages_list = []
            for row in team_members_rows:
                valid_submission_id = get_valid_completed_submission_id_for_member(row['team_member_email'], TEAM_AVERAGE_DATA_WINDOW_DAYS, all_category_keys, conn)
                if valid_submission_id:
                    individual_avgs = get_individual_averages_for_submission(valid_submission_id, conn)
                    if individual_avgs: valid_individual_averages_list.append(individual_avgs)
            num_valid_respondents = len(valid_individual_averages_list)
            if num_valid_respondents < MIN_RESPONDENTS_FOR_TEAM_AVERAGE:
                st.warning(f"Not enough recent completions ({num_valid_respondents} found, {MIN_RESPONDENTS_FOR_TEAM_AVERAGE} required) to calculate averages."); return
            df_individual_averages = pd.DataFrame(valid_individual_averages_list)
            calculated_team_averages = {}
            for cat_key_calc in all_category_keys:
                avg_col_name_calc = f"{cat_key_calc}_avg"
                if avg_col_name_calc in df_individual_averages.columns:
                    mean_val = np.nanmean(df_individual_averages[avg_col_name_calc])
                    calculated_team_averages[avg_col_name_calc] = round(mean_val, 2) if not np.isnan(mean_val) else None
            current_reporting_period = datetime.now().strftime('%Y-%m')
            if save_team_overall_averages_to_db(admin_org_name_param, admin_email_param, current_reporting_period, calculated_team_averages, num_valid_respondents, conn):
                st.success(f"Team averages for {admin_org_name_param} updated with {num_valid_respondents} respondents.")
                st.session_state.latest_team_averages_display = get_latest_team_overall_averages(admin_org_name_param, current_reporting_period, conn)
            else: st.error("Failed to save team averages.")
        except Error as e: st.error(f"Error during team average calculation: {e}")
        finally: close_db_connection(conn)
        st.rerun()

    # --- Streamlit App UI and Logic Execution ---
    if 'page_config_set' not in st.session_state:
        st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
        st.session_state.page_config_set = True

    if 'db_tables_checked' not in st.session_state:
        conn_init = get_db_connection()
        if conn_init:
            create_team_overall_averages_table(conn_init)
            close_db_connection(conn_init)
            st.session_state.db_tables_checked = True
    
    set_background(bg_path)
    display_branding_and_logout_placeholder(logo_path)

    st.markdown('<div class="logout-button-container">', unsafe_allow_html=True)
    if st.button("⏻", key="logout_button_survey_page", help="Logout"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        navigate_to("login"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if 'submission_status_checked' not in st.session_state or st.session_state.get('current_user_for_status_check') != user_email:
        submission_info = get_or_create_active_submission(user_email)
        if not submission_info: st.error("Could not initialize survey session."); return
        st.session_state.submission_info = submission_info
        st.session_state.current_submission_id = submission_info.get('submission_id')
        st.session_state.submission_action = submission_info['action']
        st.session_state.submission_message = submission_info['message']
        st.session_state.submission_status_checked = True
        st.session_state.current_user_for_status_check = user_email
        st.session_state.user_role = get_user_role(user_email)
        st.session_state.is_admin_for_reminders = is_admin_of_an_organisation(user_email)
        st.session_state.latest_team_averages_display = None
        st.rerun()
    
    submission_action = st.session_state.get('submission_action', '')
    current_submission_id = st.session_state.get('current_submission_id')
    
    # Display the primary action message (e.g., "Welcome back", "Dashboard is ready", etc.)
    if st.session_state.get('submission_message'):
        st.info(st.session_state.submission_message)

    COMPLETED_SURVEY_ACTIONS = {'VIEW_DASHBOARD_RECENT_COMPLETE', 'FINISHED_DASHBOARD_READY','VIEW_THANKS_RECENT_COMPLETE_ATHLETE', 'FINISHED_ATHLETE','VIEW_WAITING_RECENT_COMPLETE_OTHER', 'FINISHED_WAITING'}

    # Show dashboard button or final messages
    if submission_action == 'VIEW_DASHBOARD_RECENT_COMPLETE':
        if st.button("View My Dashboard", key="view_dashboard_cta", use_container_width=True): navigate_to("Dashboard")
    
    # Load survey progress data if it hasn't been loaded for this session
    if "responses" not in st.session_state or st.session_state.get('submission_id_loaded_for_survey') != current_submission_id:
        st.session_state.responses, st.session_state.saved_categories, st.session_state.category_avgs = load_user_progress(user_email, current_submission_id, survey_questions, likert_options)
        st.session_state.submission_id_loaded_for_survey = current_submission_id
        st.session_state.selected_category = None

    # --- Admin Panel Logic (Refined) ---
    is_admin = st.session_state.get('is_admin_for_reminders')
    is_on_main_screen = st.session_state.get('selected_category') is None
    admin_has_completed_survey = st.session_state.get('submission_action') in COMPLETED_SURVEY_ACTIONS

    if is_admin and is_on_main_screen:
        st.markdown("---")
        if admin_has_completed_survey:
            admin_org_details = get_admin_organisation_details(user_email)
            admin_org_name = admin_org_details['organisation_name'] if admin_org_details else "Your Organisation"
            with st.expander(f"Admin Panel: Manage Surveys & Team Averages for {admin_org_name}", expanded=True):
                # ... (The full admin panel code is here) ...
                tab1, tab2 = st.tabs(["Survey Reminders", "Team Averages"])
                with tab1:
                    team_members_status, _ = get_team_members_and_status(user_email)
                    if not team_members_status: st.info("No team members found.")
                    else:
                        df_team_status = pd.DataFrame(team_members_status); st.dataframe(df_team_status[['name', 'email', 'status_display']], use_container_width=True, hide_index=True)
                        remindable_members = [m for m in team_members_status if m['needs_reminder']]
                        if not remindable_members: st.success("All team members are up-to-date!")
                        else:
                            if st.button(f"Send Reminders to {len(remindable_members)} Member(s)", key="admin_send_reminders_button"):
                                admin_user_details_for_email = get_user_details(user_email)
                                admin_name_for_email_send = f"{admin_user_details_for_email['first_name']} {admin_user_details_for_email['last_name']}" if admin_user_details_for_email else user_email
                                sent_reminders, failed_reminders = 0, 0
                                with st.spinner("Sending reminders..."):
                                    for member_to_remind in remindable_members:
                                        if send_survey_reminder_email(member_to_remind['email'], member_to_remind['name'], admin_name_for_email_send, admin_org_name): sent_reminders += 1
                                        else: failed_reminders += 1
                                if sent_reminders > 0: st.success(f"Sent {sent_reminders} reminder(s).")
                                if failed_reminders > 0: st.warning(f"Failed to send {failed_reminders} reminder(s).")
                                st.rerun()
                with tab2:
                    st.subheader(f"Team Overall Averages for {admin_org_name}")
                    _, valid_for_calc_count = get_team_members_and_status(user_email)
                    st.write(f"Members with valid recent completions: **{valid_for_calc_count}**")
                    if valid_for_calc_count >= MIN_RESPONDENTS_FOR_TEAM_AVERAGE:
                        if st.button(f"Calculate/Recalculate Averages for {datetime.now().strftime('%B %Y')}", key="admin_calc_team_avg_button"):
                            with st.spinner(f"Calculating averages..."): handle_calculate_team_averages(user_email, admin_org_name)
                    else: st.info(f"At least {MIN_RESPONDENTS_FOR_TEAM_AVERAGE} valid completion(s) required. Currently: {valid_for_calc_count}.")
                    current_reporting_period_display = datetime.now().strftime('%Y-%m')
                    if st.session_state.get('latest_team_averages_display') is None:
                        conn_display = get_db_connection()
                        if conn_display:
                            st.session_state.latest_team_averages_display = get_latest_team_overall_averages(admin_org_name, current_reporting_period_display, conn_display)
                            close_db_connection(conn_display)
                    latest_team_avgs_data = st.session_state.get('latest_team_averages_display')
                    if latest_team_avgs_data:
                        st.write(f"**Last Calculated Averages for Period: {latest_team_avgs_data['reporting_period_identifier']}**")
                        avg_data_to_show = {cat_key_show: latest_team_avgs_data.get(f"{cat_key_show}_team_avg") for cat_key_show in all_category_keys}
                        st.dataframe(pd.Series(avg_data_to_show, name="Team Average Score").dropna().round(2), use_container_width=True)
                    else: st.write(f"No team averages calculated for {current_reporting_period_display}.")
        else:
            st.info("🔒 **Admin Panel Locked:** Please complete your own survey to unlock admin features.")

    # --- Main Survey Form ---
    if st.session_state.get('selected_category') is None:
        if submission_action not in COMPLETED_SURVEY_ACTIONS:
            st.title("QUESTIONNAIRE"); st.subheader("Choose a category to begin or continue:")
            answered_overall = sum(sum(1 for r_val in cat_resps.values() if r_val != "Select") for cat_resps in st.session_state.responses.values())
            total_overall = sum(len(q_defs) for q_defs in survey_questions.values())
            if total_overall > 0:
                progress_overall_val = answered_overall / total_overall
                st.progress(progress_overall_val); st.markdown(f"<p style='text-align:center; color:white;'>Overall Progress: {answered_overall}/{total_overall} ({progress_overall_val:.0%})</p>", unsafe_allow_html=True)
            cols = st.columns(3); prev_cat_completed_for_enable = True
            for i, cat_key_disp in enumerate(all_category_keys):
                is_cat_saved = cat_key_disp in st.session_state.saved_categories; is_btn_enabled = is_cat_saved or prev_cat_completed_for_enable
                cat_resps_current = st.session_state.responses.get(cat_key_disp, {}); answered_in_cat_disp = sum(1 for v_resp in cat_resps_current.values() if v_resp != "Select"); total_in_cat_disp = len(survey_questions[cat_key_disp])
                css_class_disp = "category-container completed" if is_cat_saved else "category-container"
                with cols[i % 3]:
                    st.markdown(f"<div class='{css_class_disp}'>", unsafe_allow_html=True)
                    if st.button(cat_key_disp, key=f"btn_{cat_key_disp}_cat", disabled=not is_btn_enabled, use_container_width=True):
                        st.session_state.selected_category = cat_key_disp; st.rerun()
                    if total_in_cat_disp > 0:
                        cat_progress_val_disp = answered_in_cat_disp / total_in_cat_disp if total_in_cat_disp > 0 else 0
                        st.progress(cat_progress_val_disp); st.caption("Completed" if is_cat_saved else f"{answered_in_cat_disp}/{total_in_cat_disp}")
                    st.markdown("</div>", unsafe_allow_html=True)
                if not is_cat_saved: prev_cat_completed_for_enable = False
            if len(st.session_state.saved_categories) == len(all_category_keys) and st.session_state.get('submission_action') == 'CONTINUE_IN_PROGRESS':
                update_submission_to_completed(current_submission_id)
                user_details_for_comp_email = get_user_details(user_email)
                user_name_for_comp_email = f"{user_details_for_comp_email['first_name']} {user_details_for_comp_email['last_name']}" if user_details_for_comp_email else user_email
                send_survey_completion_email(user_email, user_name_for_comp_email)
                st.session_state.submission_status_checked = False; st.session_state.submission_message_shown = None; st.rerun()
    else:
        current_sel_cat_form = st.session_state.selected_category
        st.subheader(f"Category: {current_sel_cat_form}"); st.markdown("---")
        qs_in_curr_cat_form = survey_questions[current_sel_cat_form]; ans_count_curr_cat_form = 0
        for q_key_form, q_text_form in qs_in_curr_cat_form.items():
            st.markdown(f"**{survey_questions[current_sel_cat_form][q_key_form]}**") # Use full text
            curr_resp_for_q_form = st.session_state.responses[current_sel_cat_form].get(q_key_form, "Select")
            try: resp_idx_form = likert_options.index(curr_resp_for_q_form)
            except ValueError: resp_idx_form = 0
            selected_val_form = st.radio("", likert_options, index=resp_idx_form, key=f"radio_{current_sel_cat_form}_{q_key_form}_{current_submission_id}", label_visibility="collapsed")
            st.session_state.responses[current_sel_cat_form][q_key_form] = selected_val_form
            if selected_val_form != "Select": ans_count_curr_cat_form += 1
        st.markdown("---"); st.markdown(f"<p style='color:#00FF7F; margin-top:15px;'><b>{ans_count_curr_cat_form} / {len(qs_in_curr_cat_form)} answered</b></p>", unsafe_allow_html=True)
        if ans_count_curr_cat_form == len(qs_in_curr_cat_form):
            is_final_cat_overall_form = (len(st.session_state.saved_categories) == len(all_category_keys) - 1 and current_sel_cat_form not in st.session_state.saved_categories)
            all_cats_already_saved_form = (len(st.session_state.saved_categories) == len(all_category_keys) and current_sel_cat_form in st.session_state.saved_categories)
            btn_text_form = "Submit Survey & Finish" if (is_final_cat_overall_form or all_cats_already_saved_form) else ("Update & Continue" if current_sel_cat_form in st.session_state.saved_categories else "Save and Continue")
            if st.button(btn_text_form, key=f"save_btn_{current_sel_cat_form}", use_container_width=True):
                avg_score_calc = save_category_to_db(current_sel_cat_form, st.session_state.responses, user_email, current_submission_id)
                if avg_score_calc is not None:
                    st.session_state.saved_categories.add(current_sel_cat_form)
                    save_category_completion(current_sel_cat_form, user_email, current_submission_id)
                    st.session_state.category_avgs[f"{current_sel_cat_form}_avg"] = avg_score_calc
                    save_averages_to_db(st.session_state.category_avgs, user_email, current_submission_id)
                    st.success(f"Progress for '{current_sel_cat_form}' saved!")
                    if len(st.session_state.saved_categories) == len(all_category_keys):
                        update_submission_to_completed(current_submission_id)
                        user_details_final_email = get_user_details(user_email)
                        user_name_final_email = f"{user_details_final_email['first_name']} {user_details_final_email['last_name']}" if user_details_final_email else user_email
                        send_survey_completion_email(user_email, user_name_final_email)
                        st.session_state.submission_status_checked = False; st.session_state.submission_message_shown = None
                    st.session_state.selected_category = None; st.rerun()
                else: st.error(f"Failed to save progress for '{current_sel_cat_form}'. Please try again.")
        else:
            st.caption("Please answer all questions in this category to save.")
