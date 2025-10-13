import streamlit as st
import base64
import mysql.connector
from mysql.connector import Error
import numpy as np
import logging
import pandas as pd

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
    Complete Streamlit function to administer the AACS survey with role-based views
    (Admin Panel, Team Dashboard) and progress resumption.
    """
    # --- Process Passed-in Secrets ---
    try:
        DB_HOST = secrets['DB_HOST']
        DB_USER = secrets['DB_USER']
        DB_PASSWORD = secrets['DB_PASSWORD']
        DB_DATABASE = "Vclarifi"
        CONFIG_LOADED_SUCCESSFULLY = True
    except (KeyError, ValueError) as e:
        logging.critical(f"FATAL: Could not read secrets. Error: {e}")
        st.error("Application is critically misconfigured. Please contact an administrator.")
        return

    # --- Paths & Constants ---
    bg_path = "images/background.jpg"
    logo_path = "images/VTARA.png"

    # --- UI & Email Helper Functions ---
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
            .logout-button-container button:hover {{ background-color: #c82333 !important; }}
            .stButton > button {{ width: 100%; padding: 15px; font-size: 18px; border-radius: 8px; background-color: #2c662d; color: white; border: none; cursor: pointer; transition: background-color 0.3s ease; }}
            .stButton > button:hover {{ background-color: #3a803d; }}
            .stButton > button:disabled {{ background-color: #a0a0a0; color: #e0e0e0; cursor: not-allowed; }}
            .category-container {{ border: 2px solid transparent; border-radius: 10px; padding: 10px; margin-bottom: 10px; background-color: rgba(0,0,0,0.3); transition: background-color 0.3s ease, border-color 0.3s ease; }}
            .category-container.completed {{ background-color: rgba(0, 123, 255, 0.2) !important; border: 2px solid #007BFF; }}
            .category-container div, .category-container p, .category-container label, .stMarkdown > p, div[data-testid="stRadio"] label span, h4, .stMetric {{ color: white !important; }}
            .stMetric .st-emotion-cache-1g8sfav {{ color: white !important; }}
            .stMetric .st-emotion-cache-nohb39 {{ color: white !important; }}
            .stCaption {{ color: rgba(255,255,255,0.9) !important; text-align: center; }}
            </style>""", unsafe_allow_html=True)
        except FileNotFoundError:
            st.warning(f"Background image not found: {image_path}")

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
        except FileNotFoundError:
            st.warning(f"Logo image not found: {logo_path_param}")

    def send_reminder_email(recipient_email, recipient_name, admin_name, team_name):
        subject = f"Reminder: Please Complete the AACS Survey for {team_name}"
        body = f"Hi {recipient_name},\n\nThis is a friendly reminder from your team administrator, {admin_name}, to complete the AACS survey for {team_name}.\n\nYour participation is crucial for our team's assessment and development."
        logging.info(f"REMINDER EMAIL SIMULATION: TO: {recipient_email}\nSUBJECT: {subject}\nBODY:\n{body}")
        st.toast(f"Reminder sent to {recipient_name}!", icon="📧")

    # --- AACS SURVEY DEFINITION ---
    likert_options = ["Select", "1: Strongly Disagree", "2: Disagree", "3: Somewhat Disagree", "4: Neutral", "5: Somewhat Agree", "6: Agree", "7: Strongly Agree"]
    survey_questions = {
        "Alignment": {"AACS1": "Our organisational goals are clearly communicated across all levels.", "AACS2": "Everyone understands how their role contributes to the wider mission.", "AACS3": "Strategic priorities are consistent and rarely change without explanation.", "AACS4": "Decision-making criteria are transparent.", "AACS5": "Leaders and staff behave consistently with our stated values.", "AACS6": "People can challenge ideas without fear of reprisal.", "AACS7": "We resolve disagreements constructively and fairly.", "AACS8": "Long-term goals and day-to-day operations are well aligned.", "AACS9": "We maintain focus even when external pressures rise.", "AACS10": "Partnerships and sponsorships reinforce our strategic direction."},
        "Agility": {"AACS11": "We identify and act on new opportunities quickly.", "AACS12": "Teams can pivot direction when conditions change.", "AACS13": "We review assumptions regularly and adjust plans as needed.", "AACS14": "Lessons from past projects are captured and applied.", "AACS15": "Mistakes are treated as learning opportunities.", "AACS16": "Feedback from stakeholders leads to visible improvements.", "AACS17": "Technology upgrades are adopted smoothly.", "AACS18": "Decision cycles are fast without sacrificing quality.", "AACS19": "We anticipate future trends rather than react to them.", "AACS20": "Cross-functional collaboration enables faster response."},
        "Capability": {"AACS21": "Processes across departments connect seamlessly.", "AACS22": "Information flows freely between teams.", "AACS23": "Tools and systems support rather than hinder collaboration.", "AACS24": "We have the right mix of skills to achieve our goals.", "AACS25": "Expertise is shared and developed internally.", "AACS26": "Professional development is prioritised.", "AACS27": "We consistently deliver projects on time and within budget.", "AACS28": "Roles and responsibilities are clearly defined.", "AACS29": "Performance standards are high and consistently met.", "AACS30": "Resource allocation is efficient and transparent."},
        "Sustainability": {"AACS31": "Workloads are manageable over the long term.", "AACS32": "The organisation supports physical and mental wellbeing.", "AACS33": "Individuals can maintain a healthy work–life balance.", "AACS34": "Decisions are guided by strong ethical principles.", "AACS35": "Diversity and inclusion are visibly valued.", "AACS36": "Integrity is recognised and rewarded.", "AACS37": "We remain effective during crises or disruptions.", "AACS38": "Contingency plans are regularly updated and tested.", "AACS39": "The organisation learns and rebounds from setbacks.", "AACS40": "We invest in long-term relationships that sustain success."}
    }
    sub_index_mapping = {
        'Communicated Intent (CI)': [f'AACS{i}' for i in range(1, 5)], 'Trust, Challenge, and Support (TCS)': [f'AACS{i}' for i in range(5, 8)], 'Strategy, Coherence, and Reinforcement (SCR)': [f'AACS{i}' for i in range(8, 11)],
        'Antennae and Vigilance (AV)': [f'AACS{i}' for i in range(11, 14)], 'Learning, Linking, and Responding (LLR)': [f'AACS{i}' for i in range(14, 17)], 'Challenge, Reframing, and Interpretation (CRI)': [f'AACS{i}' for i in range(17, 21)],
        'Systems, Integration, and Structures (SIS)': [f'AACS{i}' for i in range(21, 24)], 'Competency Development and Internalisation (CDI)': [f'AACS{i}' for i in range(24, 27)], 'Execution, Effectiveness, and Routines (EER)': [f'AACS{i}' for i in range(27, 31)],
        'Wellbeing and Balance (WBS)': [f'AACS{i}' for i in range(31, 34)], 'Ethics, Compassion, and Integrity (ECI)': [f'AACS{i}' for i in range(34, 37)], 'Resilience, Contingency, and Rebound (RCR)': [f'AACS{i}' for i in range(37, 41)]
    }
    all_domain_keys = list(survey_questions.keys())
    question_to_sub_domain = {q_id: sub_domain for sub_domain, q_list in sub_index_mapping.items() for q_id in q_list}
    
    # --- Database Interaction Functions ---
    def get_db_connection():
        try:
            return mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_DATABASE)
        except Error as e:
            st.error(f"DB Connection Error: {e}"); return None

    def close_db_connection(conn, cursor=None):
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    
    def get_user_info(email):
        conn = get_db_connection()
        if not conn: return None
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM user_registration WHERE Email_Id = %s", (email,))
                user = cursor.fetchone()
                return user
        finally:
            close_db_connection(conn)
    
    def get_user_submission_status(email):
        conn = get_db_connection()
        if not conn: return "Not Started"
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = "SELECT status FROM submissions WHERE Email_Id = %s ORDER BY start_date DESC LIMIT 1"
                cursor.execute(query, (email,))
                result = cursor.fetchone()
                return result['status'] if result else "Not Started"
        finally:
            close_db_connection(conn)

    def get_team_status(admin_email):
        conn = get_db_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (admin_email,))
                member_emails_result = cursor.fetchall()
                if not member_emails_result:
                    return []
                
                member_emails = [row['team_member_email'] for row in member_emails_result]
                
                format_strings = ','.join(['%s'] * len(member_emails))
                query = f"SELECT Email_Id, first_name, last_name FROM user_registration WHERE Email_Id IN ({format_strings})"
                cursor.execute(query, tuple(member_emails))
                members = cursor.fetchall()
                
                for member in members:
                    member['status'] = get_user_submission_status(member['Email_Id'])
                return members
        finally:
            close_db_connection(conn)

    def get_team_average_scores(admin_email):
        conn = get_db_connection()
        if not conn: return None, 0
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (admin_email,))
                member_emails_result = cursor.fetchall()
            if not member_emails_result:
                return None, 0
            member_emails = tuple(row['team_member_email'] for row in member_emails_result)

            format_strings = ','.join(['%s'] * len(member_emails))
            query = f"SELECT id FROM submissions WHERE Email_Id IN ({format_strings}) AND status = 'completed'"
            submission_ids_df = pd.read_sql(query, conn, params=member_emails)

            if submission_ids_df.empty:
                return None, 0
            
            sub_ids_list = submission_ids_df['id'].tolist()
            sub_ids_tuple = tuple(sub_ids_list)
            sub_ids_sql = str(sub_ids_tuple) if len(sub_ids_tuple) > 1 else f"({sub_ids_tuple[0]})"

            align_df = pd.read_sql(f"SELECT * FROM alignment_scores WHERE submission_id IN {sub_ids_sql}", conn)
            agile_df = pd.read_sql(f"SELECT * FROM agility_scores WHERE submission_id IN {sub_ids_sql}", conn)
            cap_df = pd.read_sql(f"SELECT * FROM capability_scores WHERE submission_id IN {sub_ids_sql}", conn)
            sustain_df = pd.read_sql(f"SELECT * FROM sustainability_scores WHERE submission_id IN {sub_ids_sql}", conn)
            pi_df = pd.read_sql(f"SELECT pi_score FROM submissions WHERE id IN {sub_ids_sql}", conn)

            avg_scores = {}
            avg_scores.update(align_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').to_dict())
            avg_scores.update(agile_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').to_dict())
            avg_scores.update(cap_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').to_dict())
            avg_scores.update(sustain_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').to_dict())
            avg_scores['pi_score'] = pi_df['pi_score'].mean()
            
            return avg_scores, len(submission_ids_df)
        finally:
            close_db_connection(conn)

    def get_or_create_active_submission(user_email_param):
        conn = get_db_connection()
        if not conn: return None
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
                    return cursor.lastrowid
        finally:
            close_db_connection(conn)

    def update_submission_to_completed(submission_id_param):
        conn = get_db_connection()
        if not conn: return False
        try:
            with conn.cursor() as cursor:
                query = "UPDATE submissions SET status = 'completed', completion_date = CURRENT_TIMESTAMP WHERE id = %s"
                cursor.execute(query, (submission_id_param,))
                conn.commit()
                return True
        finally:
            close_db_connection(conn)

    def save_domain_responses_to_db(domain_key, responses_data, submission_id_param):
        conn = get_db_connection()
        if not conn: return False
        records_to_insert = []
        for item_id, value_str in responses_data.get(domain_key, {}).items():
            if value_str != "Select":
                raw_score = int(value_str.split(":")[0])
                normalized_score = round(((raw_score - 1) / 6) * 100, 2)
                records_to_insert.append((submission_id_param, item_id, raw_score, normalized_score))
        if not records_to_insert: return True
        try:
            with conn.cursor() as cursor:
                query = "INSERT INTO aacs_responses (submission_id, item_id, raw_score, normalized_score) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE raw_score = VALUES(raw_score), normalized_score = VALUES(normalized_score)"
                cursor.executemany(query, records_to_insert)
                conn.commit()
                return True
        finally:
            close_db_connection(conn)

    def calculate_and_save_all_scores(submission_id_param):
        conn = get_db_connection()
        if not conn: return False
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT item_id, normalized_score FROM aacs_responses WHERE submission_id = %s", (submission_id_param,))
                responses = {row['item_id']: row['normalized_score'] for row in cursor.fetchall()}
            if not responses: return True
            
            scores = {}
            sub_index_abbr = {'Communicated Intent (CI)': 'CI', 'Trust, Challenge, and Support (TCS)': 'TCS', 'Strategy, Coherence, and Reinforcement (SCR)': 'SCR', 'Antennae and Vigilance (AV)': 'AV', 'Learning, Linking, and Responding (LLR)': 'LLR', 'Challenge, Reframing, and Interpretation (CRI)': 'CRI', 'Systems, Integration, and Structures (SIS)': 'SIS', 'Competency Development and Internalisation (CDI)': 'CDI', 'Execution, Effectiveness, and Routines (EER)': 'EER', 'Wellbeing and Balance (WBS)': 'WBS', 'Ethics, Compassion, and Integrity (ECI)': 'ECI', 'Resilience, Contingency, and Rebound (RCR)': 'RCR'}
            
            for name, items in sub_index_mapping.items():
                abbr = sub_index_abbr[name]
                item_scores = [responses.get(i) for i in items if i in responses]
                if item_scores: scores[abbr] = round(np.mean(item_scores), 2)
            
            domain_calcs = {'Alignment': ['CI', 'TCS', 'SCR'], 'Agility': ['AV', 'LLR', 'CRI'], 'Capability': ['SIS', 'CDI', 'EER'], 'Sustainability': ['WBS', 'ECI', 'RCR']}
            for domain, subs in domain_calcs.items():
                domain_scores_list = [scores.get(s) for s in subs if s in scores]
                if domain_scores_list: scores[domain] = round(np.mean(domain_scores_list), 2)
            
            final_domain_scores = [scores.get(d) for d in all_domain_keys if d in scores]
            if final_domain_scores: scores['PI'] = round(np.mean(final_domain_scores), 2)

            with conn.cursor() as cursor:
                align_data = {'sub_id': submission_id_param, 'CI': scores.get('CI'), 'TCS': scores.get('TCS'), 'SCR': scores.get('SCR'), 'Alignment_score': scores.get('Alignment')}
                cursor.execute("INSERT INTO alignment_scores (submission_id, CI, TCS, SCR, Alignment_score) VALUES (%(sub_id)s, %(CI)s, %(TCS)s, %(SCR)s, %(Alignment_score)s) ON DUPLICATE KEY UPDATE CI=VALUES(CI), TCS=VALUES(TCS), SCR=VALUES(SCR), Alignment_score=VALUES(Alignment_score)", align_data)
                agile_data = {'sub_id': submission_id_param, 'AV': scores.get('AV'), 'LLR': scores.get('LLR'), 'CRI': scores.get('CRI'), 'Agility_score': scores.get('Agility')}
                cursor.execute("INSERT INTO agility_scores (submission_id, AV, LLR, CRI, Agility_score) VALUES (%(sub_id)s, %(AV)s, %(LLR)s, %(CRI)s, %(Agility_score)s) ON DUPLICATE KEY UPDATE AV=VALUES(AV), LLR=VALUES(LLR), CRI=VALUES(CRI), Agility_score=VALUES(Agility_score)", agile_data)
                cap_data = {'sub_id': submission_id_param, 'SIS': scores.get('SIS'), 'CDI': scores.get('CDI'), 'EER': scores.get('EER'), 'Capability_score': scores.get('Capability')}
                cursor.execute("INSERT INTO capability_scores (submission_id, SIS, CDI, EER, Capability_score) VALUES (%(sub_id)s, %(SIS)s, %(CDI)s, %(EER)s, %(Capability_score)s) ON DUPLICATE KEY UPDATE SIS=VALUES(SIS), CDI=VALUES(CDI), EER=VALUES(EER), Capability_score=VALUES(Capability_score)", cap_data)
                sustain_data = {'sub_id': submission_id_param, 'WBS': scores.get('WBS'), 'ECI': scores.get('ECI'), 'RCR': scores.get('RCR'), 'Sustainability_score': scores.get('Sustainability')}
                cursor.execute("INSERT INTO sustainability_scores (submission_id, WBS, ECI, RCR, Sustainability_score) VALUES (%(sub_id)s, %(WBS)s, %(ECI)s, %(RCR)s, %(Sustainability_score)s) ON DUPLICATE KEY UPDATE WBS=VALUES(WBS), ECI=VALUES(ECI), RCR=VALUES(RCR), Sustainability_score=VALUES(Sustainability_score)", sustain_data)
                if scores.get('PI'):
                    cursor.execute("UPDATE submissions SET pi_score = %s WHERE id = %s", (scores['PI'], submission_id_param))
            conn.commit()
            return True
        finally:
            close_db_connection(conn)

    def save_domain_completion(domain_to_mark_completed, user_email_param, submission_id_param):
        conn = get_db_connection()
        if not conn: return
        try:
            with conn.cursor() as cursor:
                query = f"INSERT INTO accs_category_completed (Email_ID, submission_id, `{domain_to_mark_completed}`) VALUES (%s, %s, TRUE) ON DUPLICATE KEY UPDATE `{domain_to_mark_completed}` = TRUE"
                cursor.execute(query, (user_email_param, submission_id_param))
                conn.commit()
        finally:
            close_db_connection(conn)

    def load_user_progress(user_email_param, submission_id_param):
        loaded_responses = {dom_k: {q_k: "Select" for q_k in q_defs.keys()} for dom_k, q_defs in survey_questions.items()}
        completed_domains = set()
        if not submission_id_param: return loaded_responses, completed_domains
        conn = get_db_connection()
        if not conn: return loaded_responses, completed_domains
        try:
            with conn.cursor(dictionary=True, buffered=True) as cursor:
                cursor.execute("SELECT * FROM accs_category_completed WHERE Email_ID = %s AND submission_id = %s", (user_email_param, submission_id_param))
                completion_data = cursor.fetchone()
                if completion_data:
                    for domain in all_domain_keys:
                        if completion_data.get(domain): completed_domains.add(domain)
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
        finally:
            close_db_connection(conn)
        return loaded_responses, completed_domains

    # --- UI View Functions ---
    def show_survey_view(user_email):
        if 'submission_id' not in st.session_state:
            st.session_state.submission_id = get_or_create_active_submission(user_email)
            if not st.session_state.submission_id:
                st.error("Could not initialize survey session."); return
            st.session_state.responses, st.session_state.saved_domains = load_user_progress(user_email, st.session_state.submission_id)
            st.session_state.selected_domain = None
            st.rerun()

        if st.session_state.get('selected_domain') is None:
            st.title("AACS QUESTIONNAIRE")
            st.subheader("Choose a domain to begin or continue:")
            total_answered = sum(1 for resps in st.session_state.responses.values() for r in resps.values() if r != "Select")
            total_questions = sum(len(q) for q in survey_questions.values())
            progress_val = total_answered / total_questions if total_questions > 0 else 0
            st.progress(progress_val)
            st.markdown(f"<p style='text-align:center; color:white;'>Overall Progress: {total_answered}/{total_questions} ({progress_val:.0%})</p>", unsafe_allow_html=True)

            cols = st.columns(len(all_domain_keys))
            for i, domain_key in enumerate(all_domain_keys):
                is_completed = domain_key in st.session_state.saved_domains
                answered = sum(1 for r in st.session_state.responses.get(domain_key, {}).values() if r != "Select")
                total = len(survey_questions[domain_key])
                css_class = "category-container completed" if is_completed else "category-container"
                with cols[i]:
                    st.markdown(f"<div class='{css_class}'>", unsafe_allow_html=True)
                    if st.button(domain_key, key=f"btn_{domain_key}", use_container_width=True):
                        st.session_state.selected_domain = domain_key
                        st.rerun()
                    st.progress(answered / total if total > 0 else 0)
                    st.caption("Completed" if is_completed else f"{answered}/{total}")
                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            current_domain = st.session_state.selected_domain
            st.subheader(f"Domain: {current_domain}")
            
            questions_in_domain = survey_questions[current_domain]
            answered_count = 0
            current_sub_domain = ""

            for item_id, q_text in questions_in_domain.items():
                sub_domain_name = question_to_sub_domain.get(item_id, "")
                if sub_domain_name != current_sub_domain:
                    current_sub_domain = sub_domain_name
                    st.markdown(f"--- \n <h4>{current_sub_domain}</h4>", unsafe_allow_html=True)

                st.markdown(f"**{q_text}**")
                response = st.session_state.responses[current_domain].get(item_id, "Select")
                response_index = likert_options.index(response) if response in likert_options else 0
                
                selected_value = st.radio("", likert_options, index=response_index, key=f"radio_{item_id}", label_visibility="collapsed")
                st.session_state.responses[current_domain][item_id] = selected_value
                if selected_value != "Select":
                    answered_count += 1
            
            st.markdown("---")
            if answered_count == len(questions_in_domain):
                if st.button("Save and Return to Menu", key=f"save_btn_{current_domain}", use_container_width=True, type="primary"):
                    with st.spinner("Saving progress..."):
                        sub_id = st.session_state.submission_id
                        save_domain_responses_to_db(current_domain, st.session_state.responses, sub_id)
                        save_domain_completion(current_domain, user_email, sub_id)
                        calculate_and_save_all_scores(sub_id)
                        st.session_state.saved_domains.add(current_domain)
                        
                        if len(st.session_state.saved_domains) == len(all_domain_keys):
                            update_submission_to_completed(sub_id)
                            # This will be caught by the main router on the next rerun
                            st.session_state.view = 'thank_you' 
                        
                        st.session_state.selected_domain = None
                        st.rerun()
            else:
                st.caption("Please answer all questions in this domain to save.")

    def show_thank_you_view(user_info):
        st.title("✅ Thank You!")
        st.subheader("Your submission has been recorded.")
        st.balloons()
        # Admins see a button to their panel, members just see a final message.
        if user_info.get('is_admin'):
            st.success("As an administrator, you can now access your team's Admin Panel.")
            if st.button("Go to Admin Panel"):
                st.session_state.view = 'admin_panel'
                st.rerun()
        else:
            st.success("Your team administrator will be notified. You can now safely close this window.")

    def show_admin_panel(user_info):
        st.title(f"👑 Admin Panel for {user_info.get('sports_team', 'Your Team')}")
        st.markdown("---")

        with st.spinner("Loading team status..."):
            team_members = get_team_status(user_info.get('Email_Id'))
        
        if not team_members:
            st.warning("No team members are assigned to you in the admin_team_members table.")
            return

        completed_count = sum(1 for m in team_members if m['status'] == 'completed')
        all_completed = completed_count == len(team_members)

        col1, col2 = st.columns(2)
        col1.metric("Team Size", f"{len(team_members)} Members")
        col2.metric("Survey Completion", f"{completed_count} / {len(team_members)}")

        if all_completed:
            st.success("🎉 All team members have completed the survey!")
            if st.button("📈 View Team Dashboard", use_container_width=True, type="primary"):
                st.session_state.view = 'team_dashboard'
                st.rerun()
        else:
            st.info("The team dashboard will become available once all members have completed the survey.")

        st.markdown("---")
        st.subheader("Team Member Status and Reminders")

        uncompleted_members = [m for m in team_members if m['status'] != 'completed']
        if not uncompleted_members:
            st.write("All members have completed the survey.")
        else:
            selected_to_remind = st.multiselect("Select members to remind:", 
                                            options=uncompleted_members, 
                                            format_func=lambda m: f"{m.get('first_name', '')} {m.get('last_name', '')} ({m.get('status')})".strip())
            if st.button("Send Reminders to Selected", disabled=not selected_to_remind, use_container_width=True):
                admin_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                for member in selected_to_remind:
                    member_name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                    send_reminder_email(member['Email_Id'], member_name, admin_name, user_info.get('sports_team'))

    def show_team_dashboard(user_info):
        st.title(f"📈 Team Dashboard: {user_info.get('sports_team', 'Your Team')}")
        if st.button("← Back to Admin Panel"):
            st.session_state.view = 'admin_panel'
            st.rerun()
        st.markdown("---")

        with st.spinner("Calculating team averages..."):
            avg_scores, num_respondents = get_team_average_scores(user_info.get('Email_Id'))

        if not avg_scores:
            st.error("Could not retrieve team data."); return

        col1, col2 = st.columns(2)
        col1.metric("Total Respondents", num_respondents)
        col2.metric("Overall Team Performance Index (PI)", f"{avg_scores.get('pi_score', 0):.2f}")

        st.subheader("Average Domain Scores")
        domain_scores_df = pd.DataFrame({
            'Score': [
                avg_scores.get('Alignment_score', 0), avg_scores.get('Agility_score', 0),
                avg_scores.get('Capability_score', 0), avg_scores.get('Sustainability_score', 0)
            ]}, index=['Alignment', 'Agility', 'Capability', 'Sustainability'])
        st.bar_chart(domain_scores_df, y="Score")

        st.subheader("Detailed Sub-Index Breakdown")
        with st.expander("Alignment Scores"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Communicated Intent (CI)", f"{avg_scores.get('CI', 0):.2f}")
            c2.metric("Trust & Support (TCS)", f"{avg_scores.get('TCS', 0):.2f}")
            c3.metric("Strategy & Coherence (SCR)", f"{avg_scores.get('SCR', 0):.2f}")

        with st.expander("Agility Scores"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Antennae & Vigilance (AV)", f"{avg_scores.get('AV', 0):.2f}")
            c2.metric("Learning & Responding (LLR)", f"{avg_scores.get('LLR', 0):.2f}")
            c3.metric("Challenge & Interpretation (CRI)", f"{avg_scores.get('CRI', 0):.2f}")
        
        with st.expander("Capability Scores"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Systems & Integration (SIS)", f"{avg_scores.get('SIS', 0):.2f}")
            c2.metric("Competency Development (CDI)", f"{avg_scores.get('CDI', 0):.2f}")
            c3.metric("Execution & Effectiveness (EER)", f"{avg_scores.get('EER', 0):.2f}")

        with st.expander("Sustainability Scores"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Wellbeing & Balance (WBS)", f"{avg_scores.get('WBS', 0):.2f}")
            c2.metric("Ethics & Integrity (ECI)", f"{avg_scores.get('ECI', 0):.2f}")
            c3.metric("Resilience & Rebound (RCR)", f"{avg_scores.get('RCR', 0):.2f}")

    # --- Main Application Router ---
    set_background(bg_path)
    display_branding_and_logout_placeholder(logo_path)
    st.markdown('<div class="logout-button-container">', unsafe_allow_html=True)
    if st.button("⏻", key="logout_button", help="Logout"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        navigate_to("login"); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    user_info = get_user_info(user_email)
    if not user_info:
        st.error("Could not retrieve your user profile. Please contact support."); return

    # REFINED ROUTER LOGIC
    if 'view' not in st.session_state:
        user_status = get_user_submission_status(user_email)
        is_admin = user_info.get('is_admin')

        if is_admin and user_status == 'completed':
            # An admin who has completed the survey goes to the Admin Panel
            st.session_state.view = 'admin_panel'
        elif not is_admin and user_status == 'completed':
            # A non-admin who has completed goes to the Thank You page
            st.session_state.view = 'thank_you'
        else:
            # Anyone who has not completed (admin or member) must take the survey
            st.session_state.view = 'survey'

    view_map = {'admin_panel': show_admin_panel, 'team_dashboard': show_team_dashboard, 'survey': show_survey_view, 'thank_you': show_thank_you_view}
    view_func = view_map.get(st.session_state.view)
    if view_func:
        if st.session_state.view == 'survey':
            view_func(user_email)
        else:
            view_func(user_info)
