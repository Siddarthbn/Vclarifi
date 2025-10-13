import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import mysql.connector
from mysql.connector import Error
import base64
from datetime import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
# --- DATABASE & DATA FETCHING ---
# ==============================================================================

def get_db_connection(secrets):
    """Establishes database connection using secrets."""
    if not secrets:
        st.error("❌ Database connection failed: Could not load secrets.")
        return None
    try:
        return mysql.connector.connect(
            host=secrets['DB_HOST'],
            database=secrets['DB_DATABASE'],
            user=secrets['DB_USER'],
            password=secrets['DB_PASSWORD']
        )
    except (KeyError, mysql.connector.Error) as e:
        st.error(f"❌ Database connection error: {e}")
        return None

@st.cache_data(ttl=600)
def fetch_aacs_dashboard_data(_user_email, secrets):
    """Fetches and aggregates latest AACS survey data for an admin's team."""
    conn = get_db_connection(secrets)
    if not conn: return None, None

    try:
        # Step 1: Get the admin's own details
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user_registration WHERE Email_Id = %s AND is_admin = 1", (_user_email,))
            admin_info = cursor.fetchone()
        
        if not admin_info:
            st.warning("Admin user not found or does not have admin privileges.")
            return None, None
        
        org_name = admin_info.get("organisation_name")

        # Step 2: Get the list of team member emails from the mapping table
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (_user_email,))
            member_emails_result = cursor.fetchall()

        team_emails = [row['team_member_email'] for row in member_emails_result]
        # Include the admin in the analysis
        team_emails.append(_user_email)
        
        if not team_emails:
            return {}, org_name

        # Step 3: Get the latest completed submission ID for each team member
        placeholders = ','.join(['%s'] * len(team_emails))
        query = f"""
            SELECT id FROM (
                SELECT id, Email_Id, ROW_NUMBER() OVER(PARTITION BY Email_Id ORDER BY completion_date DESC) as rn
                FROM submissions
                WHERE Email_Id IN ({placeholders}) AND status = 'completed'
            ) ranked_submissions
            WHERE rn = 1
        """
        submission_ids_df = pd.read_sql(query, conn, params=tuple(team_emails))
        if submission_ids_df.empty:
            return {}, org_name

        sub_ids_list = submission_ids_df['id'].tolist()
        sub_ids_tuple = tuple(sub_ids_list)
        sub_ids_sql = str(sub_ids_tuple) if len(sub_ids_tuple) > 1 else f"({sub_ids_tuple[0]})"
        
        # Step 4: Fetch all scores for these submissions
        align_df = pd.read_sql(f"SELECT * FROM alignment_scores WHERE submission_id IN {sub_ids_sql}", conn)
        agile_df = pd.read_sql(f"SELECT * FROM agility_scores WHERE submission_id IN {sub_ids_sql}", conn)
        cap_df = pd.read_sql(f"SELECT * FROM capability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        sustain_df = pd.read_sql(f"SELECT * FROM sustainability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        pi_df = pd.read_sql(f"SELECT pi_score FROM submissions WHERE id IN {sub_ids_sql}", conn)

        # Step 5: Combine and calculate averages
        all_scores_df = pd.concat([align_df, agile_df, cap_df, sustain_df, pi_df], axis=1)
        # Remove duplicate/unnecessary columns that may result from concat
        all_scores_df = all_scores_df.loc[:, ~all_scores_df.columns.duplicated()]
        
        avg_scores = all_scores_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').round(2).to_dict()
        avg_scores['respondent_count'] = len(submission_ids_df)

        return avg_scores, org_name
    except Exception as e:
        st.error(f"❌ An error occurred during data fetching: {e}")
        return None, None
    finally:
        if conn and conn.is_connected(): conn.close()


# ==============================================================================
# --- UI, PLOTTING, AND DISPLAY FUNCTIONS ---
# ==============================================================================

def encode_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Image not found at {image_path}")
        return ""

def set_background(image_path):
    encoded_image = encode_image(image_path)
    if encoded_image:
        st.markdown(f"""<style>
            [data-testid="stAppViewContainer"] {{
                background-image: url('data:image/jpeg;base64,{encoded_image}');
                background-size: cover;
            }}
            /* Other CSS */
            </style>""", unsafe_allow_html=True) # CSS omitted for brevity

def display_header(title, logo_path, org_name):
    encoded_logo = encode_image(logo_path)
    logo_html = f'<img src="data:image/png;base64,{encoded_logo}" style="width: 50px; height: auto;">'
    st.markdown(f"""<div class="dashboard-header">
        <h1>{title}</h1><div>{logo_html}<div style='font-size: 0.5em; text-align: right;'>{org_name or ''}</div></div>
        </div>""", unsafe_allow_html=True)

def get_color_for_score(score):
    """Returns a color hex code based on a 0-100 score tier."""
    try:
        score = float(score)
        if score < 50: return '#d62728' # Red
        elif score < 75: return '#ff7f0e' # Orange
        else: return '#2ca02c'           # Green
    except (ValueError, TypeError): return '#808080' # Grey

def plot_domain_scores(scores_data, domains, benchmark=75.0):
    """Generates a bar chart for the 4 main AACS domain scores."""
    domain_scores = {domain: scores_data.get(f'{domain}_score', 0.0) for domain in domains}
    
    fig = go.Figure(go.Bar(
        x=list(domain_scores.keys()), 
        y=list(domain_scores.values()), 
        marker_color=[get_color_for_score(s) for s in domain_scores.values()],
        text=[f'{v:.1f}' for v in domain_scores.values()],
        textposition='outside', textfont_color='white'
    ))
    fig.add_shape(type="line", x0=-0.5, y0=benchmark, x1=len(domains)-0.5, y1=benchmark, line=dict(color="white", dash="dash", width=2))
    
    fig.update_layout(
        title_text="Overall Performance Across Domains", paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#1a1a1a', font_color='white', yaxis=dict(range=[0, 105])
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_sub_domain_charts(scores_data, category, sub_vars):
    """Generates donut charts for sub-domains."""
    cols = st.columns(len(sub_vars))
    for i, sub in enumerate(sub_vars):
        with cols[i]:
            score = scores_data.get(sub, 0.0)
            fig = go.Figure(go.Pie(
                values=[score, 100 - score], hole=.7,
                marker_colors=[get_color_for_score(score), '#333'],
                sort=False, textinfo='none'
            ))
            fig.update_layout(
                title_text=sub, annotations=[dict(text=f'{score:.1f}', x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')],
                showlegend=False, height=250, paper_bgcolor='rgba(0,0,0,0)', font_color='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def display_performance_highlights(org_data, sub_vars_map):
    all_scores = []
    for main_cat, sub_vars in sub_vars_map.items():
        for sub in sub_vars:
            score = org_data.get(sub, 0.0)
            if float(score) > 0:
                all_scores.append({"Sub-Domain": f"{main_cat} - {sub}", "Score": float(score)})
    
    if not all_scores:
        return None, None
    
    df_all = pd.DataFrame(all_scores)
    df_best = df_all.sort_values(by="Score", ascending=False).head(3)
    df_worst = df_all.sort_values(by="Score", ascending=True).head(3)
    return df_best, df_worst

def display_insight_text(df_best, df_worst):
    if df_best is not None and not df_best.empty:
        top_strength = df_best.iloc[0]
        strengths_text = f"The top organizational strength is **{top_strength['Sub-Domain']}** (Score: {top_strength['Score']:.1f}). This indicates a core competency that can be leveraged."
        st.markdown(f"<div class='insight-section-container'><h3><span class='strength-icon'>✅</span> Strengths</h3><p>{strengths_text}</p></div>", unsafe_allow_html=True)

    if df_worst is not None and not df_worst.empty:
        top_focus = df_worst.iloc[0]
        focus_text = f"The primary area for focus is **{top_focus['Sub-Domain']}** (Score: {top_focus['Score']:.1f}). Prioritizing improvements here could yield the greatest return."
        st.markdown(f"<div class='insight-section-container'><h3><span class='focus-icon'>🎯</span> Areas for Focus</h3><p>{focus_text}</p></div>", unsafe_allow_html=True)

# ==============================================================================
# --- MAIN DASHBOARD FUNCTION ---
# ==============================================================================

def dashboard(navigate_to, user_email, secrets, **kwargs):
    """Renders the main AACS dashboard page."""
    set_background(BG_IMAGE_PATH)

    org_data, org_name = fetch_aacs_dashboard_data(user_email, secrets)
    
    if org_data is None:
        st.warning("Dashboard data could not be loaded. Please ensure surveys have been completed by your team.")
        return

    display_header("Team Performance Dashboard", LOGO_PATH, org_name)

    sub_vars_map = {
        "Alignment": ["CI", "TCS", "SCR"],
        "Agility": ["AV", "LLR", "CRI"],
        "Capability": ["SIS", "CDI", "EER"],
        "Sustainability": ["WBS", "ECI", "RCR"]
    }
    benchmark = 75.0
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.metric("Overall Team Performance Index (PI)", f"{org_data.get('pi_score', 0):.2f}")
    with col2:
        st.metric("Total Respondents", f"{int(org_data.get('respondent_count', 0))}")

    st.markdown("---")

    col1, col2 = st.columns([2, 1.5])
    with col1:
        plot_domain_scores(org_data, sub_vars_map.keys(), benchmark=benchmark)
    
    with col2:
        st.subheader("Key Insights")
        df_best, df_worst = display_performance_highlights(org_data, sub_vars_map)
        display_insight_text(df_best, df_worst)

    st.markdown("---")
    st.subheader("Detailed Sub-Domain Analysis")
    category = st.selectbox("Select Domain to Explore", list(sub_vars_map.keys()))
    if category:
        plot_sub_domain_charts(org_data, category, sub_vars_map[category])

# ==============================================================================
# --- SCRIPT EXECUTION ---
# ==============================================================================

if __name__ == "__main__":
    # This block is for direct execution and testing.
    # In a real multi-page app, the user_email would come from st.session_state after login.
    
    # Faking secrets for local testing if AWS is not configured
    # In production, this get_aws_secrets() will be used.
    # For now, we simulate it.
    mock_secrets = {
        "DB_HOST": "your_db_host",
        "DB_USER": "your_db_user",
        "DB_PASSWORD": "your_db_password",
        "DB_DATABASE": "Vclarifi",
    }

    if 'user_email' not in st.session_state:
        # Hardcoding an admin email for testing purposes
        st.session_state.user_email = 'siddarth@vtaraenergygroup.com'

    # The navigate_to function is a placeholder for multi-page navigation
    def mock_navigate_to(page):
        st.success(f"Navigating to {page}...")

    dashboard(
        navigate_to=mock_navigate_to, 
        user_email=st.session_state.user_email,
        secrets=mock_secrets # In production, you'd pass get_aws_secrets() here.
    )
