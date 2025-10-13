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
        st.error(f"❌ An error occurred during data fetching: {e}")
        logging.error(f"Data fetching error: {e}")
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
                [data-testid="stAppViewContainer"] > .main {{
                    background-image: url('data:image/jpeg;base64,{encoded_image}');
                    background-size: cover; background-position: center;
                    background-repeat: no-repeat; background-attachment: fixed;
                }}
                [data-testid="stHeader"], [data-testid="stToolbar"] {{ background: rgba(0,0,0,0); }}
                .main .block-container {{ padding: 1rem 1.5rem; }} /* Adjust main block padding */
                
                /* Style for each individual dark container */
                .card {{
                    background-color: rgba(10, 20, 30, 0.85);
                    padding: 25px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(5px);
                    -webkit-backdrop-filter: blur(5px);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    margin-bottom: 20px;
                }}
                h1, h2, h3, h4, h5, label, .st-b3, .st-ag, .st-be, .stMetric * {{ color: white !important; }}
                .dashboard-header {{ /* This is separate from the cards */
                    background: none; box-shadow: none; border: none;
                    padding: 0 0 20px 0; font-size: 2.2em;
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

def plot_domain_comparison_bar_chart(scores_data, domains, benchmark):
    domain_names = list(domains)
    domain_scores = [scores_data.get(f'{domain}_score', 0.0) for domain in domain_names]
    fig = go.Figure(go.Bar(
        x=domain_scores, y=domain_names, orientation='h',
        marker_color=[get_color_for_score(s) for s in domain_scores],
        text=[f'{v:.1f}' for v in domain_scores], textposition='outside'
    ))
    fig.add_vline(x=benchmark, line_dash="dash", line_color="white", annotation_text="Benchmark")
    fig.update_layout(
        title_text="Domain Performance vs Benchmark", paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)', font_color='white', 
        xaxis=dict(range=[0, 105], gridcolor='rgba(255,255,255,0.2)'),
        yaxis=dict(autorange="reversed"), margin=dict(l=120)
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

def generate_dynamic_summary(pi_score, benchmark, avg_scores, domains):
    domain_scores = {domain: avg_scores.get(f'{domain}_score', 0.0) for domain in domains}
    sorted_domains = sorted(domain_scores.items(), key=lambda item: item[1])
    lowest_domain, lowest_score = sorted_domains[0]
    highest_domain, highest_score = sorted_domains[-1]
    
    summary = f"The team's **Overall Performance Index (PI) is {pi_score:.1f}**. "
    if pi_score >= benchmark:
        summary += "This indicates a strong overall performance, exceeding the benchmark. "
    else:
        summary += "This is below the benchmark and suggests opportunities for strategic growth. "

    summary += f"The highest-scoring domain is **{highest_domain}** (score: {highest_score:.1f}), representing a key organizational strength. "
    summary += f"Conversely, the primary area for development is **{lowest_domain}** (score: {lowest_score:.1f})."
    return summary

def plot_score_distribution(df_all_scores, domains, benchmark):
    selected_domain = st.selectbox("Select a Domain:", list(domains.keys()), key="dist_domain_select")
    score_col = f"{selected_domain}_score"
    if score_col in df_all_scores.columns:
        fig = px.box(df_all_scores, y=score_col, title=f"Score Distribution for {selected_domain}", points="all", color_discrete_sequence=['#007BFF'])
        fig.add_hline(y=benchmark, line_dash="dash", line_color="white", annotation_text="Benchmark", annotation_position="bottom right")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.1)', font_color='white', yaxis_title="Score", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# --- MAIN DASHBOARD FUNCTION ---
# ==============================================================================

def dashboard(navigate_to, user_email, secrets, **kwargs):
    """Renders the main AACS dashboard page with a professional UI."""
    set_background(BG_IMAGE_PATH)

    avg_scores, org_name, all_scores_df = fetch_aacs_dashboard_data(user_email, secrets)
    
    if avg_scores is None or not avg_scores:
        st.warning("Dashboard data could not be loaded. Please ensure surveys have been completed by your team.")
        return

    display_header("Team Performance Dashboard", LOGO_PATH, org_name)

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

    # --- Each section is now in its own card ---
    with card_container():
        m1, m2 = st.columns([1, 2.5])
        with m1:
            pi_score = avg_scores.get('pi_score', 0)
            st.metric("Overall PI Score", f"{pi_score:.1f}", f"{pi_score - benchmark:.1f} vs Benchmark", delta_color="off")
            st.metric("Total Respondents", f"{int(avg_scores.get('respondent_count', 0))}")
        with m2:
            st.subheader("Performance Summary")
            st.markdown(generate_dynamic_summary(pi_score, benchmark, avg_scores, sub_vars_map.keys()))
    
    with card_container():
        col1, col2 = st.columns([1.5, 1])
        with col1:
            plot_domain_comparison_bar_chart(avg_scores, sub_vars_map, benchmark)
        with col2:
            st.subheader("Key Performance Insights")
            if df_best is not None and not df_best.empty:
                st.markdown("<h5><span class='strength-icon'>✅</span> Top 3 Strengths</h5>", unsafe_allow_html=True)
                for _, row in df_best.iterrows():
                    st.markdown(f"<div class='highlight-card'><p><b>{row['Sub-Domain']}</b> (Score: {row['Score']:.1f})</p></div>", unsafe_allow_html=True)
            if df_worst is not None and not df_worst.empty:
                st.markdown("<h5 style='margin-top: 20px;'><span class='focus-icon'>🎯</span> Top 3 Areas for Focus</h5>", unsafe_allow_html=True)
                for _, row in df_worst.iterrows():
                    st.markdown(f"<div class='highlight-card'><p><b>{row['Sub-Domain']}</b> (Score: {row['Score']:.1f})</p></div>", unsafe_allow_html=True)

    with card_container():
        st.subheader("Detailed Analysis")
        tab1, tab2 = st.tabs(["Sub-Domain Drill-Down", "Score Distribution"])
        with tab1:
            st.write("Explore the individual components of each domain.")
            category = st.selectbox("Select Domain to Explore", list(sub_vars_map.keys()))
            if category:
                plot_sub_domain_charts(avg_scores, sub_vars_map[category], sub_abbr_to_full)
        with tab2:
            st.write("Analyze the range and variance of scores across team members for each domain.")
            if all_scores_df is not None and not all_scores_df.empty:
                plot_score_distribution(all_scores_df, sub_vars_map, benchmark)

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
