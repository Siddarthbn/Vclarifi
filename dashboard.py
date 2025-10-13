import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector
from mysql.connector import Error
import base64
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
    """Fetches and aggregates latest AACS survey data for an admin's team, returning both averages and individual scores."""
    conn = get_db_connection(secrets)
    if not conn: return None, None, None

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user_registration WHERE Email_Id = %s AND is_admin = 1", (_user_email,))
            admin_info = cursor.fetchone()
        
        if not admin_info:
            st.warning("Admin user not found or does not have admin privileges.")
            return None, None, None
        
        org_name = admin_info.get("organisation_name")

        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT team_member_email FROM admin_team_members WHERE admin_email = %s", (_user_email,))
            member_emails_result = cursor.fetchall()

        team_emails = [row['team_member_email'] for row in member_emails_result]
        team_emails.append(_user_email)
        
        if not team_emails:
            return {}, org_name, pd.DataFrame()

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
            return {}, org_name, pd.DataFrame()

        sub_ids_list = submission_ids_df['id'].tolist()
        sub_ids_tuple = tuple(sub_ids_list)
        sub_ids_sql = str(sub_ids_tuple) if len(sub_ids_tuple) > 1 else f"({sub_ids_tuple[0]})"
        
        align_df = pd.read_sql(f"SELECT * FROM alignment_scores WHERE submission_id IN {sub_ids_sql}", conn)
        agile_df = pd.read_sql(f"SELECT * FROM agility_scores WHERE submission_id IN {sub_ids_sql}", conn)
        cap_df = pd.read_sql(f"SELECT * FROM capability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        sustain_df = pd.read_sql(f"SELECT * FROM sustainability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        pi_df = pd.read_sql(f"SELECT id as submission_id, pi_score FROM submissions WHERE id IN {sub_ids_sql}", conn)

        all_scores_df = align_df
        for df in [agile_df, cap_df, sustain_df, pi_df]:
            all_scores_df = pd.merge(all_scores_df, df, on="submission_id", how="outer")
        
        all_scores_df = all_scores_df.loc[:, ~all_scores_df.columns.duplicated()]

        avg_scores = all_scores_df.mean(numeric_only=True).drop(['id', 'submission_id'], errors='ignore').round(2).to_dict()
        avg_scores['respondent_count'] = len(submission_ids_df)

        return avg_scores, org_name, all_scores_df
    except Exception as e:
        st.error(f"❌ An error occurred during data fetching: {e}")
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

def set_background(image_path):
    encoded_image = encode_image(image_path)
    if encoded_image:
        st.markdown(f"""
            <style>
                [data-testid="stAppViewContainer"] {{
                    background-image: url('data:image/jpeg;base64,{encoded_image}');
                    background-size: cover;
                }}
                [data-testid="stHeader"], [data-testid="stToolbar"] {{ background: rgba(0,0,0,0); }}
                .card-container {{
                    background-color: rgba(10, 20, 30, 0.7);
                    padding: 25px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                    backdrop-filter: blur(4px);
                    -webkit-backdrop-filter: blur(4px);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                }}
                h1, h2, h3, h4, h5, label, .st-b3, .st-ag, .st-be, .stMetric * {{ color: white !important; }}
                .main .block-container {{ padding: 2rem 1.5rem; }}
                .dashboard-header {{
                    background-color: rgba(0,0,0,0.8); color: white; padding: 20px 30px; border-radius: 10px;
                    margin-bottom: 30px; font-size: 2.5em; font-weight: bold;
                    display: flex; justify-content: space-between; align-items: center;
                }}
                .highlight-card {{
                    background-color: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.2); margin-bottom: 10px;
                }}
                .highlight-card p {{ color: white !important; margin-bottom: 0; }}
                .strength-icon {{ color: #2ca02c; }} .focus-icon {{ color: #ff7f0e; }}
            </style>
        """, unsafe_allow_html=True)

def display_header(title, logo_path, org_name):
    encoded_logo = encode_image(logo_path)
    logo_html = f'<img src="data:image/png;base64,{encoded_logo}" style="width: 50px; height: auto;">'
    st.markdown(f"""<div class="dashboard-header">
        <div>{title}</div><div style="text-align: right;">{logo_html}<div style='font-size: 0.5em;'>{org_name or ''}</div></div>
        </div>""", unsafe_allow_html=True)

def get_color_for_score(score):
    try:
        score = float(score)
        if score < 50: return '#d62728'
        elif score < 75: return '#ff7f0e'
        else: return '#2ca02c'
    except (ValueError, TypeError): return '#808080'

def plot_radar_chart(scores_data, domains):
    """Generates a radar chart for the 4 main AACS domain scores."""
    domain_scores = [scores_data.get(f'{domain}_score', 0.0) for domain in domains]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=domain_scores + [domain_scores[0]],
        theta=domains + [domains[0]],
        fill='toself',
        marker_color='rgba(0, 123, 255, 0.7)',
        name='Team Average'
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], color='white', gridcolor='rgba(255,255,255,0.3)'),
            angularaxis=dict(color='white', linecolor='rgba(255,255,255,0.3)')
        ),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='white',
        title='Holistic Performance Overview'
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
                marker_colors=[get_color_for_score(score), 'rgba(255,255,255,0.1)'],
                sort=False, textinfo='none'
            ))
            fig.update_layout(
                title_text=sub, annotations=[dict(text=f'{score:.1f}', x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')],
                showlegend=False, height=250, margin=dict(t=40, b=0, l=0, r=0),
                paper_bgcolor='rgba(0,0,0,0)', font_color='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def display_performance_highlights(org_data, sub_vars_map):
    all_scores = [{'Sub-Domain': sub, 'Domain': main, 'Score': float(org_data.get(sub, 0.0))} 
                  for main, subs in sub_vars_map.items() for sub in subs if org_data.get(sub)]
    if not all_scores:
        return None, None
    df = pd.DataFrame(all_scores)
    return df.sort_values(by="Score", ascending=False).head(3), df.sort_values(by="Score", ascending=True).head(3)

def plot_score_distribution(df_all_scores, domains, benchmark):
    st.subheader("Score Distribution Analysis")
    selected_domain = st.selectbox("Select a Domain to see score distribution:", domains)
    score_col = f"{selected_domain}_score"
    if score_col in df_all_scores.columns:
        fig = px.box(df_all_scores, y=score_col, title=f"Distribution of Scores for {selected_domain}", points="all",
                     color_discrete_sequence=['#007BFF'])
        fig.add_hline(y=benchmark, line_dash="dash", line_color="white", annotation_text="Benchmark", annotation_position="bottom right")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.1)', font_color='white')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No distribution data available for this domain.")


# ==============================================================================
# --- MAIN DASHBOARD FUNCTION ---
# ==============================================================================

def dashboard(navigate_to, user_email, secrets, **kwargs):
    """Renders the main AACS dashboard page with a professional UI."""
    set_background(BG_IMAGE_PATH)

    avg_scores, org_name, all_scores_df = fetch_aacs_dashboard_data(user_email, secrets)
    
    if not avg_scores:
        st.warning("Dashboard data could not be loaded. Please ensure surveys have been completed by your team.")
        return

    display_header("Team Performance Dashboard", LOGO_PATH, org_name)

    sub_vars_map = {
        "Alignment": ["CI", "TCS", "SCR"], "Agility": ["AV", "LLR", "CRI"],
        "Capability": ["SIS", "CDI", "EER"], "Sustainability": ["WBS", "ECI", "RCR"]
    }
    benchmark = 75.0
    
    df_best, df_worst = display_performance_highlights(avg_scores, sub_vars_map)

    # --- Top Metrics Row ---
    st.markdown('<div class="card-container" style="margin-bottom: 20px;">', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    pi_score = avg_scores.get('pi_score', 0)
    m1.metric("Overall PI Score", f"{pi_score:.1f}", f"{pi_score - benchmark:.1f} vs Benchmark", delta_color="off")
    m2.metric("Total Respondents", f"{int(avg_scores.get('respondent_count', 0))}")
    if df_best is not None and not df_best.empty:
        m3.metric("Top Performing Area", df_best.iloc[0]['Sub-Domain'], f"Score: {df_best.iloc[0]['Score']:.1f}")
    if df_worst is not None and not df_worst.empty:
        m4.metric("Area for Focus", df_worst.iloc[0]['Sub-Domain'], f"Score: {df_worst.iloc[0]['Score']:.1f}")
    st.markdown('</div>', unsafe_allow_html=True)

    # --- Main Content Columns ---
    col1, col2 = st.columns([2, 1])

    with col1:
        with st.container():
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            plot_radar_chart(avg_scores, list(sub_vars_map.keys()))
            st.markdown("---")
            st.subheader("Detailed Domain Drill-Down")
            tabs = st.tabs(list(sub_vars_map.keys()))
            for i, (domain, sub_domains) in enumerate(sub_vars_map.items()):
                with tabs[i]:
                    plot_sub_domain_charts(avg_scores, domain, sub_domains)
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            st.subheader("Key Performance Insights")
            if df_best is not None and not df_best.empty:
                st.markdown("<h5><span class='strength-icon'>✅</span> Top 3 Strengths</h5>", unsafe_allow_html=True)
                for _, row in df_best.iterrows():
                    st.markdown(f"<div class='highlight-card'><p><b>{row['Sub-Domain']}</b> (Score: {row['Score']:.1f})</p></div>", unsafe_allow_html=True)
            
            if df_worst is not None and not df_worst.empty:
                st.markdown("<h5 style='margin-top: 20px;'><span class='focus-icon'>🎯</span> Top 3 Areas for Focus</h5>", unsafe_allow_html=True)
                for _, row in df_worst.iterrows():
                    st.markdown(f"<div class='highlight-card'><p><b>{row['Sub-Domain']}</b> (Score: {row['Score']:.1f})</p></div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="card-container" style="margin-top: 20px;">', unsafe_allow_html=True)
            if all_scores_df is not None and not all_scores_df.empty:
                plot_score_distribution(all_scores_df, list(sub_vars_map.keys()), benchmark)
            st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# --- SCRIPT EXECUTION ---
# ==============================================================================

if __name__ == "__main__":
    # This block is for direct execution and local testing.
    # Replace mock_secrets with your actual database credentials for local development.
    mock_secrets = {
        "DB_HOST": "localhost",
        "DB_USER": "your_db_user",
        "DB_PASSWORD": "your_db_password",
        "DB_DATABASE": "Vclarifi",
    }

    if 'user_email' not in st.session_state:
        # Hardcode an admin email from your database for testing
        st.session_state.user_email = 'siddarth@vtaraenergygroup.com'

    # The navigate_to function is a placeholder for multi-page navigation
    def mock_navigate_to(page):
        st.success(f"Navigating to {page}...")

    dashboard(
        navigate_to=mock_navigate_to, 
        user_email=st.session_state.user_email,
        secrets=mock_secrets
    )
