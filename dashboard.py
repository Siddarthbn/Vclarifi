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

# --- CONSTANTS AND MAPPINGS ---
SUB_DOMAIN_FULL_NAMES = {
    "CI": "Clarity of Intent", "TCS": "Team Cohesion & Synergy", "SCR": "Strategic & Customer Relevance",
    "AV": "Adaptability & Velocity", "LLR": "Learning, Listening & Responding", "CRI": "Continuous & Rapid Innovation",
    "SIS": "Systems, Information & Structure", "CDI": "Competency & Digital Mindset", "EER": "Empowerment & Enabling Risk",
    "WBS": "Wellness & Balanced Scorecard", "ECI": "Ethical Conduct & Integrity", "RCR": "Responsible Corporate Citizenship"
}

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
        team_emails.append(_user_email) # Include the admin in the analysis
        
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
        
        # REFINED: Select specific columns to avoid duplicate 'id' columns from each table
        align_df = pd.read_sql(f"SELECT submission_id, CI, TCS, SCR, Alignment_score FROM alignment_scores WHERE submission_id IN {sub_ids_sql}", conn)
        agile_df = pd.read_sql(f"SELECT submission_id, AV, LLR, CRI, Agility_score FROM agility_scores WHERE submission_id IN {sub_ids_sql}", conn)
        cap_df = pd.read_sql(f"SELECT submission_id, SIS, CDI, EER, Capability_score FROM capability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        sustain_df = pd.read_sql(f"SELECT submission_id, WBS, ECI, RCR, Sustainability_score FROM sustainability_scores WHERE submission_id IN {sub_ids_sql}", conn)
        pi_df = pd.read_sql(f"SELECT id as submission_id, pi_score FROM submissions WHERE id IN {sub_ids_sql}", conn)

        # Merge all dataframes on the common 'submission_id' column
        all_scores_df = align_df
        for df in [agile_df, cap_df, sustain_df, pi_df]:
            all_scores_df = pd.merge(all_scores_df, df, on="submission_id", how="outer")
        
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
                    background-color: rgba(10, 20, 30, 0.75);
                    padding: 25px;
                    border-radius: 15px;
                    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                    backdrop-filter: blur(5px);
                    -webkit-backdrop-filter: blur(5px);
                    border: 1px solid rgba(255, 255, 255, 0.18);
                    margin-bottom: 20px; /* Add margin to separate containers */
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
                .stButton button {{
                    background-color: #007bff;
                    color: white;
                    font-weight: bold;
                    border-radius: 10px;
                    border: 1px solid #007bff;
                }}
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
        if score < 50: return '#d62728' # Red
        elif score < 75: return '#ff7f0e' # Orange
        else: return '#2ca02c'           # Green
    except (ValueError, TypeError): return '#808080' # Grey

def plot_domain_comparison_bar_chart(scores_data, domains, benchmark):
    """Generates a bar chart for the 4 main AACS domain scores with benchmark."""
    domain_names = list(domains.keys())
    domain_scores = [scores_data.get(f'{domain}_score', 0.0) for domain in domains]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=domain_names, 
        y=domain_scores, 
        marker_color=[get_color_for_score(s) for s in domain_scores],
        text=[f'{v:.1f}' for v in domain_scores],
        textposition='outside', 
        textfont_color='white'
    ))
    fig.add_shape(type="line", x0=-0.5, y0=benchmark, x1=len(domain_names)-0.5, y1=benchmark,
                  line=dict(color="white", dash="dash", width=2),
                  name='Benchmark')
    
    fig.update_layout(
        title_text="Domain Performance Comparison", 
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(255,255,255,0.1)', 
        font_color='white', 
        yaxis=dict(range=[0, 105], gridcolor='rgba(255,255,255,0.1)'),
        xaxis=dict(tickangle=-45)
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_sub_domain_charts(scores_data, sub_vars):
    """Generates donut charts for sub-domains."""
    cols = st.columns(len(sub_vars))
    for i, sub in enumerate(sub_vars):
        with cols[i]:
            score = scores_data.get(sub, 0.0)
            full_name = SUB_DOMAIN_FULL_NAMES.get(sub, sub)
            fig = go.Figure(go.Pie(
                values=[score, 100 - score], hole=.7,
                marker_colors=[get_color_for_score(score), 'rgba(255,255,255,0.1)'],
                sort=False, textinfo='none'
            ))
            fig.update_layout(
                title_text=full_name, annotations=[dict(text=f'{score:.1f}', x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')],
                showlegend=False, height=250, margin=dict(t=40, b=0, l=0, r=0),
                paper_bgcolor='rgba(0,0,0,0)', font_color='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def get_performance_highlights(org_data, sub_vars_map):
    all_scores = [{'Sub-Domain_Short': sub, 'Sub-Domain': SUB_DOMAIN_FULL_NAMES.get(sub, sub), 'Domain': main, 'Score': float(org_data.get(sub, 0.0))} 
                  for main, subs in sub_vars_map.items() for sub in subs if sub in org_data and org_data.get(sub) is not None]
    
    if not all_scores:
        return None, None
    
    df = pd.DataFrame(all_scores)
    df_best = df.sort_values(by="Score", ascending=False).head(3)
    df_worst = df.sort_values(by="Score", ascending=True).head(3)
    return df_best, df_worst

def generate_dynamic_summary(pi_score, benchmark, df_best, df_worst):
    summary = f"The team's **Overall Performance Index (PI) is {pi_score:.1f}**"
    
    if pi_score >= benchmark:
        summary += ", indicating a strong performance **above the benchmark**."
    else:
        summary += ", which is **below the benchmark** and suggests areas for strategic improvement."

    if df_best is not None and not df_best.empty:
        top_strength = df_best.iloc[0]
        summary += f" A significant strength lies in **{top_strength['Sub-Domain']}** (score: {top_strength['Score']:.1f}), showing a solid foundation."
    
    if df_worst is not None and not df_worst.empty:
        top_focus = df_worst.iloc[0]
        summary += f" For targeted development, **{top_focus['Sub-Domain']}** (score: {top_focus['Score']:.1f}) is identified as a primary area for improvement."

    summary += " Continuous focus on these insights can further enhance team effectiveness."
    return summary

def plot_score_distribution(df_all_scores, domains, benchmark):
    st.subheader("Score Distribution Across Team Members")
    selected_domain = st.selectbox("Select a Domain:", list(domains.keys()), key="dist_domain_select")
    score_col = f"{selected_domain}_score"
    
    if score_col in df_all_scores.columns:
        fig = px.box(df_all_scores, y=score_col, title=f"Score Distribution for {selected_domain}", points="all",
                         color_discrete_sequence=['#007BFF'])
        fig.add_hline(y=benchmark, line_dash="dash", line_color="white", annotation_text="Benchmark", annotation_position="bottom right")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.1)', font_color='white',
                                yaxis_title="Score", xaxis_title="")
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
    
    if avg_scores is None or not avg_scores:
        st.warning("Dashboard data could not be loaded. Please ensure surveys have been completed by your team and the database is accessible.")
        return

    display_header("Team Performance Dashboard", LOGO_PATH, org_name)

    sub_vars_map = {
        "Alignment": ["CI", "TCS", "SCR"], "Agility": ["AV", "LLR", "CRI"],
        "Capability": ["SIS", "CDI", "EER"], "Sustainability": ["WBS", "ECI", "RCR"]
    }
    benchmark = 75.0
    
    df_best, df_worst = get_performance_highlights(avg_scores, sub_vars_map)

    # --- Top Metrics Row ---
    with st.container():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        pi_score = avg_scores.get('pi_score', 0)
        m1.metric("Overall PI Score", f"{pi_score:.1f}", f"{pi_score - benchmark:.1f} vs Benchmark", delta_color="off")
        m2.metric("Total Respondents", f"{int(avg_scores.get('respondent_count', 0))}")
        if df_best is not None and not df_best.empty:
            m3.metric("Top Performing Area", df_best.iloc[0]['Sub-Domain'], f"Score: {df_best.iloc[0]['Score']:.1f}")
        if df_worst is not None and not df_worst.empty:
            m4.metric("Area for Focus", df_worst.iloc[0]['Sub-Domain'], f"Score: {df_worst.iloc[0]['Score']:.1f}")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Performance Summary and Overview Plots ---
    col1, col2 = st.columns([2, 1])

    with col1:
        with st.container():
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            st.subheader("Performance Summary")
            st.markdown(generate_dynamic_summary(pi_score, benchmark, df_best, df_worst))
            st.markdown('</div>', unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="card-container">', unsafe_allow_html=True)
            plot_domain_comparison_bar_chart(avg_scores, sub_vars_map, benchmark)
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

    # --- Detailed Sub-Domain Analysis ---
    with st.container():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.subheader("Detailed Sub-Domain Analysis")
        tabs = st.tabs(list(sub_vars_map.keys()))
        for i, (domain, sub_domains) in enumerate(sub_vars_map.items()):
            with tabs[i]:
                plot_sub_domain_charts(avg_scores, sub_domains)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Score Distribution ---
    with st.container():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        if all_scores_df is not None and not all_scores_df.empty:
            plot_score_distribution(all_scores_df, sub_vars_map, benchmark)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Recommendations Button ---
    with st.container():
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.subheader("Next Steps")
        st.markdown("Click below to view tailored recommendations based on your team's performance.")
        if st.button("View Recommendations ➔", use_container_width=True, key="recommend_button"):
            navigate_to("Recommendations")
        st.markdown('</div>', unsafe_allow_html=True)

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
