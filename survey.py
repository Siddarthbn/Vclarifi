import streamlit as st
import base64
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import numpy as np
import logging

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Vclarifi AACS",
    page_icon="images/VTARA.png",
    layout="wide"
)

# ---------- LOGGING CONFIGURATION ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# ---------- MAIN SURVEY FUNCTION ----------
def survey(navigate_to, user_email, secrets):
    """
    Complete Streamlit function to administer the AACS survey.
    """
    # --- Process Passed-in Secrets ---
    try:
        if secrets:
            DB_HOST = secrets['DB_HOST']
            DB_USER = secrets['DB_USER']
            DB_PASSWORD = secrets['DB_PASSWORD']
            DB_DATABASE = "Vclarifi"  # Assuming the same database
            CONFIG_LOADED_SUCCESSFULLY = True
            logging.info("Configuration secrets successfully processed.")
        else:
            raise ValueError("Received an empty secrets object.")
    except (KeyError, ValueError) as e:
        logging.critical(f"FATAL: Could not read secrets passed into function. Check keys. Error: {e}")
        DB_HOST = DB_DATABASE = DB_USER = DB_PASSWORD = None
        CONFIG_LOADED_SUCCESSFULLY = False

    # --- Initial Configuration Check ---
    if not CONFIG_LOADED_SUCCESSFULLY:
        st.error("Application is critically misconfigured. Cannot initialize survey. Please contact an administrator.")
        return

    # --- Paths & Constants ---
    bg_path = "images/background.jpg"
    logo_path = "images/VTARA.png"

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
            .category-container {{ border: 2px solid transparent; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: rgba(0,0,0,0.3); transition: background-color 0.3s ease, border-color 0.3s ease; }}
            .category-container.completed {{ background-color: rgba(0, 123, 255, 0.2) !important; border: 2px solid #007BFF; }}
            .category-container div, .category-container p, .category-container label, .stMarkdown > p, div[data-testid="stRadio"] label span {{ color: white !important; }}
            .stCaption {{ color: rgba(255,255,255,0.9) !important; text-align: center; }}
            </style>""", unsafe_allow_html=True)
        except FileNotFoundError:
            st.warning(f"Background image not found: {image_path}")
        except Exception as e:
            st.error(f"Error setting background: {e}")

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
        except FileNotFoundError:
            st.warning(f"Logo image not found: {logo_path_param}")
        except Exception as e:
            st.error(f"Error displaying logo: {e}")

    # --- Email Sending Utilities (Placeholder) ---
    def send_survey_completion_email(recipient_email, recipient_name):
        # Add your email sending logic here if needed
        logging.info(f"Generated survey completion email for {recipient_name} at {recipient_email}")
        pass

    # --- AACS SURVEY DEFINITION ---
    likert_options = [
        "Select", "1: Strongly Disagree", "2: Disagree", "3: Somewhat Disagree",
        "4: Neutral", "5: Somewhat Agree", "6: Agree", "7: Strongly Agree"
    ]
    survey_questions = {
        "Alignment": {
            "AACS1": "Our organisational goals are clearly communicated across all levels.",
            "AACS2": "Everyone understands how their role contributes to the wider mission.",
            "AACS3": "Strategic priorities are consistent and rarely change without explanation.",
            "AACS4": "Decision-making criteria are transparent.",
            "AACS5": "Leaders and staff behave consistently with our stated values.",
            "AACS6": "People can challenge ideas without fear of reprisal.",
            "AACS7": "We resolve disagreements constructively and fairly.",
            "AACS8": "Long-term goals and day-to-day operations are well aligned.",
            "AACS9": "We maintain focus even when external pressures rise.",
            "AACS10": "Partnerships and sponsorships reinforce our strategic direction."
        },
        "Agility": {
            "AACS11": "We identify and act on new opportunities quickly.",
            "AACS12": "Teams can pivot direction when conditions change.",
            "AACS13": "We review assumptions regularly and adjust plans as needed.",
            "AACS14": "Lessons from past projects are captured and applied.",
            "AACS15": "Mistakes are treated as learning opportunities.",
            "AACS16": "Feedback from stakeholders leads to visible improvements.",
            "AACS17": "Technology upgrades are adopted smoothly.",
            "AACS18": "Decision cycles are fast without sacrificing quality.",
            "AACS19": "We anticipate future trends rather than react to them.",
            "AACS20": "Cross-functional collaboration enables faster response."
        },
        "Capability": {
            "AACS21": "Processes across departments connect seamlessly.",
            "AACS22": "Information flows freely between teams.",
            "AACS23": "Tools and systems support rather than hinder collaboration.",
            "AACS24": "We have the right mix of skills to achieve our goals.",
            "AACS25": "Expertise is shared and developed internally.",
            "AACS26": "Professional development is prioritised.",
            "AACS27": "We consistently deliver projects on time and within budget.",
            "AACS28": "Roles and responsibilities are clearly defined.",
            "AACS29": "Performance standards are high and consistently met.",
            "AACS30": "Resource allocation is efficient and transparent."
        },
        "Sustainability": {
            "AACS31": "Workloads are manageable over the long term.",
            "AACS32": "The organisation supports physical and mental wellbeing.",
            "AACS33": "Individuals can maintain a healthy work–life balance.",
            "AACS34": "Decisions are guided by strong ethical principles.",
            "AACS35": "Diversity and inclusion are visibly valued.",
            "AACS36": "Integrity is recognised and rewarded.",
            "AACS37": "We remain effective during crises or disruptions.",
            "AACS38": "Contingency plans are regularly updated and tested.",
            "AACS39": "The organisation learns and rebounds from setbacks.",
            "AACS40": "We invest in long-term relationships that sustain success."
        }
    }
    sub_index_mapping = {
        'CI':  [f'AACS{i}' for i in range(1, 5)],   'TCS': [f'AACS{i}' for i in range(5, 8)],   'SCR': [f'AACS{i}' for i in range(8, 11)],
        'AV':  [f'AACS{i}' for i in range(11, 14)], 'LLR': [f'AACS{i}' for i in range(14, 17)], 'CRI': [f'AACS{i}' for i in range(17, 21)],
        'SIS': [f'AACS{i}' for i in range(21, 24)], 'CDI': [f'AACS{i}' for i in range(24, 27)], 'EER': [f'AACS{i}' for i in range(27, 31)],
        'WBS': [f'AACS{i}' for i in range(31, 34)], 'ECI': [f'AACS{i}' for i in range(34, 37)], 'RCR': [f'AACS{i}' for i in range(37, 41)]
    }
    all_domain_keys = list(survey_questions.keys())

    # --- Database Interaction Functions ---
    def get_db_connection():
        try:
            conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_DATABASE)
            if conn.is_connected():
                return conn
        except Error as e:
            st.error(f"Failed to connect to the database: {e}")
            return None
        return None

    def close_db_connection(conn, cursor=None):
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    def get_user_details(user_email_param):
        conn = get_db_connection()
        if not conn:
            return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT first_name, last_name FROM admin_team_members WHERE Email_Id = %s", (user_email_param,))
                user = cursor.fetchone()
                if user:
                    return user
                cursor.execute("SELECT first_name, last_name FROM user_registration WHERE Email_Id = %s", (user_email_param,))
                user = cursor.fetchone()
                return user
        except Error as e:
            st.error(f"Error fetching user details: {e}")
            return None
        finally:
            close_db_connection(conn)

    def get_or_create_active_submission(user_email_param):
        conn = get_db_connection()
        if not conn:
            return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = "SELECT id FROM submissions WHERE Email_Id = %s AND status = 'in-progress' ORDER BY start_date DESC LIMIT 1"
                cursor.execute(query, (user_email_param,))
                submission = cursor.fetchone()
                if submission:
                    return submission['id']
                else:
                    insert_query = "INSERT INTO submissions (Email_Id, status) VALUES (%s, 'in-progress')"
                    cursor.execute(insert_query, (user_email_param,))
                    conn.commit()
                    logging.info(f"Created new submission with ID {cursor.lastrowid} for user {user_email_param}")
                    return cursor.lastrowid
        except Error as e:
            st.error(f"Error managing submission session: {e}")
            conn.rollback()
            return None
        finally:
            close_db_connection(conn)

    def update_submission_to_completed(submission_id_param):
        conn = get_db_connection()
        if not conn:
            return False
        try:
            with conn.cursor() as cursor:
                query = "UPDATE submissions SET status = 'completed', completion_date = CURRENT_TIMESTAMP WHERE id = %s"
                cursor.execute(query, (submission_id_param,))
                conn.commit()
                return True
        except Error as e:
            st.error(f"Error finalizing submission: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)

    def save_domain_responses_to_db(domain_key, responses_data, submission_id_param):
        conn = get_db_connection()
        if not conn:
            return False
        domain_responses = responses_data.get(domain_key, {})
        if not domain_responses:
            return True
        records_to_insert = []
        for item_id, value_str in domain_responses.items():
            if value_str != "Select":
                try:
                    raw_score = int(value_str.split(":")[0])
                    normalized_score = round(((raw_score - 1) / (7 - 1)) * 100, 2)
                    records_to_insert.append((submission_id_param, item_id, raw_score, normalized_score))
                except (ValueError, IndexError):
                    continue
        if not records_to_insert:
            return True
        try:
            with conn.cursor() as cursor:
                query = """
                    INSERT INTO aacs_responses (submission_id, item_id, raw_score, normalized_score)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        raw_score = VALUES(raw_score),
                        normalized_score = VALUES(normalized_score)
                """
                cursor.executemany(query, records_to_insert)
                conn.commit()
                logging.info(f"Successfully saved {len(records_to_insert)} responses for submission {submission_id_param}.")
                return True
        except Error as e:
            st.error(f"MySQL Error saving responses: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)

    def calculate_and_save_all_scores(submission_id_param):
        conn = get_db_connection()
        if not conn:
            return False
        scores = {}
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT item_id, normalized_score FROM aacs_responses WHERE submission_id = %s", (submission_id_param,))
                responses = {row['item_id']: row['normalized_score'] for row in cursor.fetchall()}
            if not responses:
                return True

            for sub_index, items in sub_index_mapping.items():
                item_scores = [responses.get(item) for item in items if responses.get(item) is not None]
                if item_scores:
                    scores[sub_index] = round(np.mean(item_scores), 2)
            
            scores['Alignment'] = round(np.mean([scores.get(si) for si in ['CI', 'TCS', 'SCR'] if scores.get(si) is not None]), 2) if any(k in scores for k in ['CI', 'TCS', 'SCR']) else None
            scores['Agility'] = round(np.mean([scores.get(si) for si in ['AV', 'LLR', 'CRI'] if scores.get(si) is not None]), 2) if any(k in scores for k in ['AV', 'LLR', 'CRI']) else None
            scores['Capability'] = round(np.mean([scores.get(si) for si in ['SIS', 'CDI', 'EER'] if scores.get(si) is not None]), 2) if any(k in scores for k in ['SIS', 'CDI', 'EER']) else None
            scores['Sustainability'] = round(np.mean([scores.get(si) for si in ['WBS', 'ECI', 'RCR'] if scores.get(si) is not None]), 2) if any(k in scores for k in ['WBS', 'ECI', 'RCR']) else None

            domain_scores = [scores.get(d) for d in all_domain_keys if scores.get(d) is not None]
            if domain_scores:
                scores['PI'] = round(np.mean(domain_scores), 2)

            with conn.cursor() as cursor:
                align_data = {'sub_id': submission_id_param, 'CI': scores.get('CI'), 'TCS': scores.get('TCS'), 'SCR': scores.get('SCR'), 'Alignment_score': scores.get('Alignment')}
                cursor.execute("""INSERT INTO alignment_scores (submission_id, CI, TCS, SCR, Alignment_score) VALUES (%(sub_id)s, %(CI)s, %(TCS)s, %(SCR)s, %(Alignment_score)s) ON DUPLICATE KEY UPDATE CI=VALUES(CI), TCS=VALUES(TCS), SCR=VALUES(SCR), Alignment_score=VALUES(Alignment_score)""", align_data)
                
                agile_data = {'sub_id': submission_id_param, 'AV': scores.get('AV'), 'LLR': scores.get('LLR'), 'CRI': scores.get('CRI'), 'Agility_score': scores.get('Agility')}
                cursor.execute("""INSERT INTO agility_scores (submission_id, AV, LLR, CRI, Agility_score) VALUES (%(sub_id)s, %(AV)s, %(LLR)s, %(CRI)s, %(Agility_score)s) ON DUPLICATE KEY UPDATE AV=VALUES(AV), LLR=VALUES(LLR), CRI=VALUES(CRI), Agility_score=VALUES(Agility_score)""", agile_data)
                
                cap_data = {'sub_id': submission_id_param, 'SIS': scores.get('SIS'), 'CDI': scores.get('CDI'), 'EER': scores.get('EER'), 'Capability_score': scores.get('Capability')}
                cursor.execute("""INSERT INTO capability_scores (submission_id, SIS, CDI, EER, Capability_score) VALUES (%(sub_id)s, %(SIS)s, %(CDI)s, %(EER)s, %(Capability_score)s) ON DUPLICATE KEY UPDATE SIS=VALUES(SIS), CDI=VALUES(CDI), EER=VALUES(EER), Capability_score=VALUES(Capability_score)""", cap_data)
                
                sustain_data = {'sub_id': submission_id_param, 'WBS': scores.get('WBS'), 'ECI': scores.get('ECI'), 'RCR': scores.get('RCR'), 'Sustainability_score': scores.get('Sustainability')}
                cursor.execute("""INSERT INTO sustainability_scores (submission_id, WBS, ECI, RCR, Sustainability_score) VALUES (%(sub_id)s, %(WBS)s, %(ECI)s, %(RCR)s, %(Sustainability_score)s) ON DUPLICATE KEY UPDATE WBS=VALUES(WBS), ECI=VALUES(ECI), RCR=VALUES(RCR), Sustainability_score=VALUES(Sustainability_score)""", sustain_data)
                
                if 'PI' in scores:
                    cursor.execute("UPDATE submissions SET pi_score = %s WHERE id = %s", (scores['PI'], submission_id_param))

            conn.commit()
            logging.info(f"Successfully calculated and saved scores for submission {submission_id_param}.")
            return True

        except Error as e:
            st.error(f"MySQL Error calculating or saving scores: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)

    def save_domain_completion(domain_to_mark_completed, user_email_param, submission_id_param):
        conn = get_db_connection()
        if not domain_to_mark_completed or not conn:
            return
        try:
            with conn.cursor() as cursor:
                col_name = f"`{domain_to_mark_completed}`"
                # UPDATED TABLE NAME
                query = f"""
                    INSERT INTO accs_category_completed (Email_ID, submission_id, {col_name})
                    VALUES (%s, %s, TRUE)
                    ON DUPLICATE KEY UPDATE {col_name} = TRUE
                """
                cursor.execute(query, (user_email_param, submission_id_param))
                conn.commit()
        except Error as e:
            st.error(f"MySQL Error updating domain completion: {e}")
            conn.rollback()
        finally:
            close_db_connection(conn)

    def load_user_progress(user_email_param, submission_id_param):
        loaded_responses = {dom_k: {q_k: "Select" for q_k in q_defs.keys()} for dom_k, q_defs in survey_questions.items()}
        completed_domains = set()
        if not submission_id_param:
            return loaded_responses, completed_domains

        conn = get_db_connection()
        if not conn:
            return loaded_responses, completed_domains

        try:
            with conn.cursor(dictionary=True, buffered=True) as cursor:
                # UPDATED TABLE NAME
                cursor.execute("SELECT * FROM accs_category_completed WHERE Email_ID = %s AND submission_id = %s", (user_email_param, submission_id_param))
                completion_data = cursor.fetchone()
                if completion_data:
                    for domain in all_domain_keys:
                        if completion_data.get(domain):
                            completed_domains.add(domain)

                cursor.execute("SELECT item_id, raw_score FROM aacs_responses WHERE submission_id = %s", (submission_id_param,))
                saved_answers = {row['item_id']: row['raw_score'] for row in cursor.fetchall()}

                for domain, questions in survey_questions.items():
                    for item_id in questions.keys():
                        if item_id in saved_answers:
                            raw_score = saved_answers[item_id]
                            for option in likert_options:
                                if option.startswith(str(raw_score) + ":"):
                                    loaded_responses[domain][item_id] = option
                                    break
        except Error as e:
            st.error(f"MySQL Error loading progress: {e}")
        finally:
            close_db_connection(conn)
        return loaded_responses, completed_domains

    # --- Streamlit App UI and Logic Execution ---
    set_background(bg_path)
    display_branding_and_logout_placeholder(logo_path)

    st.markdown('<div class="logout-button-container">', unsafe_allow_html=True)
    if st.button("⏻", key="logout_button_survey_page", help="Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        navigate_to("login")
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if 'submission_id' not in st.session_state:
        current_submission_id = get_or_create_active_submission(user_email)
        if not current_submission_id:
            st.error("Could not initialize survey session. Please contact support.")
            return
        st.session_state.submission_id = current_submission_id
        st.session_state.responses, st.session_state.saved_domains = load_user_progress(user_email, current_submission_id)
        st.session_state.selected_domain = None
        st.rerun()

    current_submission_id = st.session_state.submission_id

    # --- Survey Taking View ---
    if st.session_state.get('selected_domain') is None:
        st.title("AACS QUESTIONNAIRE")
        st.subheader("Choose a domain to begin or continue:")

        total_answered = sum(1 for domain_resps in st.session_state.responses.values() for r_val in domain_resps.values() if r_val != "Select")
        total_questions = sum(len(q_defs) for q_defs in survey_questions.values())
        progress_val = total_answered / total_questions if total_questions > 0 else 0
        st.progress(progress_val)
        st.markdown(f"<p style='text-align:center; color:white;'>Overall Progress: {total_answered}/{total_questions} ({progress_val:.0%})</p>", unsafe_allow_html=True)

        cols = st.columns(len(all_domain_keys))
        for i, domain_key in enumerate(all_domain_keys):
            is_completed = domain_key in st.session_state.saved_domains
            domain_resps = st.session_state.responses.get(domain_key, {})
            answered_in_domain = sum(1 for r in domain_resps.values() if r != "Select")
            total_in_domain = len(survey_questions[domain_key])
            
            css_class = "category-container completed" if is_completed else "category-container"
            with cols[i]:
                st.markdown(f"<div class='{css_class}'>", unsafe_allow_html=True)
                if st.button(domain_key, key=f"btn_{domain_key}", use_container_width=True):
                    st.session_state.selected_domain = domain_key
                    st.rerun()
                
                domain_progress = answered_in_domain / total_in_domain if total_in_domain > 0 else 0
                st.progress(domain_progress)
                st.caption("Completed" if is_completed else f"{answered_in_domain}/{total_in_domain}")
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        # --- Question Answering Screen ---
        current_domain = st.session_state.selected_domain
        st.subheader(f"Domain: {current_domain}")
        st.markdown("---")

        questions_in_domain = survey_questions[current_domain]
        answered_count = 0
        for item_id, q_text in questions_in_domain.items():
            st.markdown(f"**{q_text}**")
            current_response = st.session_state.responses[current_domain].get(item_id, "Select")
            try:
                response_index = likert_options.index(current_response)
            except ValueError:
                response_index = 0
            
            selected_value = st.radio("", likert_options, index=response_index, key=f"radio_{current_domain}_{item_id}_{current_submission_id}", label_visibility="collapsed")
            st.session_state.responses[current_domain][item_id] = selected_value
            if selected_value != "Select":
                answered_count += 1
        
        st.markdown("---")
        st.markdown(f"<p style='color:#00FF7F; margin-top:15px;'><b>{answered_count} / {len(questions_in_domain)} answered</b></p>", unsafe_allow_html=True)

        if answered_count == len(questions_in_domain):
            is_final_domain = (len(st.session_state.saved_domains) == len(all_domain_keys) - 1 and current_domain not in st.session_state.saved_domains)
            all_domains_saved = (len(st.session_state.saved_domains) == len(all_domain_keys))
            
            btn_text = "Submit Survey & Finish" if (is_final_domain or all_domains_saved) else \
                       ("Update & Return to Menu" if current_domain in st.session_state.saved_domains else "Save and Return to Menu")

            if st.button(btn_text, key=f"save_btn_{current_domain}", use_container_width=True):
                with st.spinner("Saving progress..."):
                    if save_domain_responses_to_db(current_domain, st.session_state.responses, current_submission_id):
                        st.session_state.saved_domains.add(current_domain)
                        save_domain_completion(current_domain, user_email, current_submission_id)
                        calculate_and_save_all_scores(current_submission_id)

                        st.success(f"Progress for '{current_domain}' saved!")

                        if len(st.session_state.saved_domains) == len(all_domain_keys):
                            update_submission_to_completed(current_submission_id)
                            user_details = get_user_details(user_email)
                            user_name = f"{user_details['first_name']} {user_details['last_name']}" if user_details else user_email
                            send_survey_completion_email(user_email, user_name)
                            # Clear session to force a fresh state on next login or action
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            st.success("Survey submitted successfully! You will be logged out.")
                            navigate_to("login")
                        
                        st.session_state.selected_domain = None
                        st.rerun()
                    else:
                        st.error(f"Failed to save progress for '{current_domain}'. Please try again.")
        else:
            st.caption("Please answer all questions in this domain to save.")
