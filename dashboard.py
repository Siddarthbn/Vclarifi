import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector
from mysql.connector import Error
import base64
import os
from contextlib import contextmanager
import logging

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Vclarifi Dashboard",
    page_icon="images/VTARA.png",
    layout="wide"
)

# ---------- LOGGING CONFIGURATION ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# --- ROBUST PATH HANDLING ---
LOGO_PATH = os.path.join("images", "VTARA.png")
BG_IMAGE_PATH = os.path.join("images", "background.jpg")

# ==============================================================================
# --- DATABASE & DATA FETCHING (Unchanged) ---
# ==============================================================================
# All data fetching functions are unchanged and included for completeness.

def get_db_connection(secrets):
    if not secrets: st.error("❌ DB connection failed: Secrets not loaded."); return None
    try:
        return mysql.connector.connect(
            host=secrets['DB_HOST'], database=secrets['DB_DATABASE'],
            user=secrets['DB_USER'], password=secrets['DB_PASSWORD']
        )
    except (KeyError, mysql.connector.Error) as e:
        st.error(f"❌ DB connection error: {e}"); return None

@st.cache_data(ttl=600)
def fetch_aacs_dashboard_data(_user_email, secrets):
    conn = get_db_connection(secrets)
    if not conn: return None, None, None
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user_registration WHERE Email_Id = %s AND is_admin = 1", (_user_email,))
            admin_info = cursor.fetchone()
        if not admin_info:
            st.warning("Admin user not found or does not have admin privileges."); return None, None, None
        org_name = admin_info.get("organisation_name")
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (_user_email,))
            member_emails_result = cursor.fetchall()
        team_emails = [row['team_member_email'] for row in member_emails_result]
        team_emails.append(_user_email)
        if not team_emails: return {}, org_name, pd.DataFrame()

        placeholders = ','.join(['%s'] * len(team_emails))
        query = f"SELECT id FROM (SELECT id, Email_Id, ROW_NUMBER() OVER(PARTITION BY Email_Id ORDER BY completion_date DESC) as rn FROM submissions WHERE Email_Id IN ({placeholders}) AND status = 'completed') ranked_submissions WHERE rn = 1"
        submission_ids_df = pd.read_sql(query, conn, params=tuple(team_emails))
        if submission_ids_df.empty: return {}, org_name, pd.DataFrame()

        sub_ids_list = submission_ids_df['id'].tolist()
        sub_ids_tuple = tuple(sub_ids_list)
        sub_ids_sql = str(sub_ids_tuple) if len(sub_ids_tuple) > 1 else f"({sub_ids_tuple[0]})"
        
        align_df = pd.read_sql(f"SELECT submission_id, CI, TCS, SCR, Alignment_score FROM alignment_scores WHERE submission_id IN {sub_ids_sql}", conn)
        agile_df = pd.read_sql(f"SELECT submission_id, AV, LLR, CRI, Agility_score FROM agility_scores WHERE submission_id IN {sub_ids_sql}", conn)
        cap_df = pd.read_sql(f"SELECT submission_id, SIS, CDI, EER, Capability_score FROM capability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        sustain_df = pd.read_sql(f"SELECT submission_id, WBS, ECI, RCR, Sustainability_score FROM sustainability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        pi_df = pd.read_sql(f"SELECT id as submission_id, pi_score FROM submissions WHERE id IN {sub_ids_sql}", conn)

        all_scores_df = pd.merge(align_df, agile_df, on="submission_id", how="outer")
        all_scores_df = pd.merge(all_scores_df, cap_df, on="submission_id", how="outer")
        all_scores_df = pd.merge(all_scores_df, sustain_df, on="submission_id", how="outer")
        all_scores_df = pd.merge(all_scores_df, pi_df, on="submission_id", how="outer")
        
        avg_scores = all_scores_df.mean(numeric_only=True).drop(['submission_id'], errors='ignore').round(2).to_dict()
        avg_scores['respondent_count'] = len(submission_ids_df)
        return avg_scores, org_name, all_scores_df
    except Exception as e:
        st.error(f"❌ An error occurred during data fetching: {e}"); logging.error(f"Data fetching error: {e}")
        return None, None, None
    finally:
        if conn and conn.is_connected(): conn.close()

# ==============================================================================
# --- UI, PLOTTING, AND DISPLAY FUNCTIONS ---
# ==============================================================================

def encode_image(image_path):
    try:
        with open(image_path, "rb") as img_file: return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError: st.warning(f"Image not found at {image_path}"); return ""

@contextmanager
def card_container():
    """A context manager to wrap content in a styled card container."""
    st.markdown('<div class="card">', unsafe_allow_html=True)
    yield
    st.markdown('</div>', unsafe_allow_html=True)

def set_background(image_path):
    encoded_image = encode_image(image_path)
    if encoded_image:
        st.markdown(f"""
            <style>
                body {{
                    background-image: url('data:image/jpeg;base64,{encoded_image}');
                    background-size: cover; background-position: center;
                    background-repeat: no-repeat; background-attachment: fixed;
                }}
                [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main, [data-testid="stHeader"], [data-testid="stToolbar"] {{
                    background: transparent;
                }}
                .main .block-container {{
                    padding: 1rem 1.5rem; max-width: 95%; margin: 1rem auto;
                }}
                .card {{
                    background-color: rgba(0, 0, 0, 0.75);
                    padding: 25px; border-radius: 15px;
                    margin-bottom: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
                }}
                h1, h2, h3, h4, h5, label, p, .st-b3, .st-ag, .st-be, .stMetric * {{ color: white !important; }}
                .strength-icon {{ color: #2ca02c; }} .focus-icon {{ color: #ff7f0e; }}
            </style>
        """, unsafe_allow_html=True)

def display_header(title, logo_path, org_name):
    st.markdown(f"<h1 style='text-align: center; color: white;'>{title}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: #ccc; margin-top: -10px;'>{org_name or ''}</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)

def get_color_for_score(score):
    try:
        score = float(score)
        if score < 50: return '#d62728'
        elif score < 75: return '#ff7f0e'
        else: return '#2ca02c'
    except (ValueError, TypeError): return '#808080'

def plot_radar_chart(scores_data, domains):
    domain_scores = [scores_data.get(f'{domain}_score', 0.0) for domain in domains]
    fig = go.Figure(go.Scatterpolar(
        r=domain_scores + [domain_scores[0]], theta=domains + [domains[0]],
        fill='toself', marker_color='rgba(0, 123, 255, 0.7)'
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], color='white', gridcolor='rgba(255,255,255,0.3)'),
            angularaxis=dict(color='white', linecolor='rgba(255,255,255,0.3)')
        ),
        showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='white', title='Holistic Performance Overview', margin=dict(t=80, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_sub_domain_charts(scores_data, sub_vars, sub_abbr_to_full):
    cols = st.columns(len(sub_vars))
    for i, sub_abbr in enumerate(sub_vars):
        with cols[i]:
            score = scores_data.get(sub_abbr, 0.0)
            full_name = sub_abbr_to_full.get(sub_abbr, sub_abbr)
            fig = go.Figure(go.Pie(
                values=[score, 100 - score], hole=.7,
                marker_colors=[get_color_for_score(score), 'rgba(255,255,255,0.1)'],
                sort=False, textinfo='none', direction='clockwise'
            ))
            fig.update_layout(
                title_text=full_name, annotations=[dict(text=f'{score:.1f}', x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')],
                showlegend=False, height=250, margin=dict(t=40, b=0, l=0, r=0),
                paper_bgcolor='rgba(0,0,0,0)', font_color='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def get_performance_highlights(org_data, sub_vars_map, sub_abbr_to_full):
    all_scores = [{'Sub-Domain': sub_abbr_to_full.get(sub, sub), 'Score': float(org_data.get(sub, 0.0))} 
                  for main, subs in sub_vars_map.items() for sub in subs if sub in org_data and org_data.get(sub) is not None]
    if not all_scores: return None, None
    df = pd.DataFrame(all_scores)
    return df.sort_values(by="Score", ascending=False).head(3), df.sort_values(by="Score", ascending=True).head(3)

# ==============================================================================
# --- MAIN DASHBOARD FUNCTION ---
# ==============================================================================

def dashboard(navigate_to, user_email, secrets, **kwargs):
    set_background(BG_IMAGE_PATH)
    avg_scores, org_name, all_scores_df = fetch_aacs_dashboard_data(user_email, secrets)
    
    display_header("Team Performance Dashboard", LOGO_PATH, org_name)

    if avg_scores is None or not avg_scores:
        st.warning("Dashboard data could not be loaded. Please ensure surveys have been completed by your team.")
        return

    sub_vars_map = {
        "Alignment": ["CI", "TCS", "SCR"], "Agility": ["AV", "LLR", "CRI"],
        "Capability": ["SIS", "CDI", "EER"], "Sustainability": ["WBS", "ECI", "RCR"]
    }
    sub_abbr_to_full = {
        "CI": "Communicated Intent", "TCS": "Trust & Support", "SCR": "Strategy & Coherence",
        "AV": "Antennae & Vigilance", "LLR": "Learning & Responding", "CRI": "Challenge & Interpretation",
        "SIS": "Systems & Integration", "CDI": "Competency Development", "EER": "Execution & Effectiveness",
        "WBS": "Wellbeing & Balance", "ECI": "Ethics & Integrity", "RCR": "Resilience & Rebound"
    }
    benchmark = 75.0
    
    df_best, df_worst = get_performance_highlights(avg_scores, sub_vars_map, sub_abbr_to_full)

    # --- Top Metrics Row ---
    with card_container():
        m1, m2, m3, m4 = st.columns(4)
        pi_score = avg_scores.get('pi_score', 0)
        m1.metric("Overall PI Score", f"{pi_score:.1f}", f"{pi_score - benchmark:.1f} vs Benchmark", delta_color="off")
        m2.metric("Total Respondents", f"{int(avg_scores.get('respondent_count', 0))}")
        if df_best is not None and not df_best.empty:
            m3.metric("Top Performing Area", df_best.iloc[0]['Sub-Domain'], f"Score: {df_best.iloc[0]['Score']:.1f}")
        if df_worst is not None and not df_worst.empty:
            m4.metric("Area for Focus", df_worst.iloc[0]['Sub-Domain'], f"Score: {df_worst.iloc[0]['Score']:.1f}")

    # --- Main Visuals & Insights Columns ---
    col1, col2 = st.columns([2, 1])
    with col1:
        with card_container():
            st.subheader("Performance Overview")
            plot_radar_chart(avg_scores, list(sub_vars_map.keys()))
    with col2:
        with card_container():
            st.subheader("Key Insights")
            if df_best is not None and not df_best.empty:
                st.markdown("<h5><span class='strength-icon'>✅</span> Top 3 Strengths</h5>", unsafe_allow_html=True)
                for _, row in df_best.iterrows():
                    st.markdown(f"**{row['Sub-Domain']}**: {row['Score']:.1f}")
            st.markdown("---")
            if df_worst is not None and not df_worst.empty:
                st.markdown("<h5><span class='focus-icon'>🎯</span> Top 3 Areas for Focus</h5>", unsafe_allow_html=True)
                for _, row in df_worst.iterrows():
                    st.markdown(f"**{row['Sub-Domain']}**: {row['Score']:.1f}")
    
    # --- Detailed Sub-Domain Analysis ---
    with card_container():
        st.subheader("Detailed Sub-Domain Analysis")
        category = st.selectbox("Select Domain to Explore", list(sub_vars_map.keys()))
        if category:
            plot_sub_domain_charts(avg_scores, sub_vars_map[category], sub_abbr_to_full)

    # --- NEW: Recommendations Button ---
    with card_container():
        st.subheader("Next Steps")
        st.write("Based on these results, you can explore tailored suggestions for improvement.")
        if st.button("Explore Recommendations 💡", use_container_width=True, type="primary"):
            navigate_to("Recommendations")


# ==============================================================================
# --- SCRIPT EXECUTION ---
# ==============================================================================

if __name__ == "__main__":
    mock_secrets = {
        "DB_HOST": "localhost",
        "DB_USER": "your_db_user",
        "DB_PASSWORD": "your_db_password",
        "DB_DATABASE": "Vclarifi",
    }
    if 'user_email' not in st.session_state:
        st.session_state.user_email = 'siddarth@vtaraenergygroup.com'
    def mock_navigate_to(page):
        st.success(f"Navigating to {page}...")
    dashboard(
        navigate_to=mock_navigate_to, 
        user_email=st.session_state.user_email,
        secrets=mock_secrets
    )
