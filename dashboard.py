import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import mysql.connector
import base64
from datetime import datetime
import io
from PIL import Image
import os

# For Email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# --- Imports for AWS Secrets Manager ---
import boto3
import json
import logging

# --- Use os.path.join for robust path handling ---
LOGO_PATH = os.path.join("images", "vtara.png")
BG_IMAGE_PATH = os.path.join("images", "bg.jpg")


# ==============================================================================
# --- AWS SECRETS MANAGER HELPER ---
# ==============================================================================

@st.cache_data(ttl=600)  # Cache secrets for 10 minutes to reduce API calls
def get_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.
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
        logging.error(f"AWS Secrets Manager Error: {e}")
        st.error("FATAL: Could not retrieve application secrets from AWS.")
        st.error("Please contact support and check IAM permissions and secret name.")
        return None

# -------------------- UI Helpers --------------------
def encode_image(image_path):
    """Encodes an image to a base64 string for embedding in HTML."""
    if not os.path.exists(image_path):
        st.warning(f"DEBUG: File does not exist at path: {os.path.abspath(image_path)}. Please verify the file location.")
        return ""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.error(f"Error encoding image {image_path}: {e}")
        return ""

def set_background(image_path, default_color_hex="#438454"):
    """Sets the overall background as an image or a default color."""
    bg_style = ""
    if image_path and os.path.exists(image_path):
        encoded_image = encode_image(image_path)
        if encoded_image:
            lower_path = image_path.lower()
            mime_type = "application/octet-stream"
            if lower_path.endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            elif lower_path.endswith(".png"):
                mime_type = "image/png"
            bg_style = f"""
                background-image: url('data:{mime_type};base64,{encoded_image}');
                background-size: cover; background-position: center;
                background-repeat: no-repeat; background-attachment: fixed;
            """
        else:
            bg_style = f"background-color: {default_color_hex};"
    else:
        bg_style = f"background-color: {default_color_hex};"

    st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{ {bg_style} }}
        [data-testid="stHeader"], [data-testid="stToolbar"] {{ background: rgba(0,0,0,0); }}
        .main .block-container {{
            background-color: rgba(0,0,0,0.7); color: white; padding: 0px 40px 40px 40px;
            border-radius: 15px; box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            margin-top: 50px; margin-bottom: 50px; max-width: 95vw;
        }}
        [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] {{ padding-top: 40px; }}
        .dashboard-header {{
            background-color: #000000; color: white; padding: 20px 30px; border-radius: 10px;
            margin-bottom: 30px; font-size: 2.5em; font-weight: bold;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2); display: flex;
            justify-content: space-between; align-items: center;
        }}
        h1, h2, h3, h4, h5, h6, label, .st-b3, .st-ag, .st-be {{ color: white !important; }}
        .stDataFrame th {{ background-color: #333333; color: white; }}
        .stDataFrame td {{ background-color: #1a1a1a; color: white; }}
        .stSelectbox > div[data-baseweb="select"] > div:first-child {{
            background-color: #333333 !important; border: 1px solid #555555 !important;
        }}
        .score-tiers-container {{
            display: flex; align-items: center; gap: 10px; margin-top: 10px;
        }}
        .score-tiers-container > div {{
            display: flex; align-items: center; gap: 3px; font-size: 0.75em;
        }}
        .insight-section-container {{
            background-color: #1a1a1a; padding: 15px; border-radius: 8px;
            margin-top: 15px; min-height: 180px; border: 1px solid #333333;
        }}
        /* MODIFIED CSS: Ensure text inside insight box is white */
        .insight-section-container p {{
            color: white !important;
            text-align: justify;
        }}
        .strength-icon {{ color: #2ca02c; }} .focus-icon {{ color: #ff7f0e; }}
        </style>
    """, unsafe_allow_html=True)

def display_header_with_logo_and_text(title, logo_path, org_name):
    """Displays a custom header with a title, logo, and organization name."""
    encoded_logo = encode_image(logo_path)
    logo_html = f'<img src="data:image/png;base64,{encoded_logo}" style="width: 50px; height: auto;">' if encoded_logo else ''
    org_display_html = f"<div>{org_name or 'Organization'}</div>"
    st.markdown(f"""
        <div class="dashboard-header">
            <h1>{title}</h1><div>{logo_html}{org_display_html}</div>
        </div>
    """, unsafe_allow_html=True)

# -------------------- Data Access --------------------
def get_db_connection():
    """Establishes database connection using a flat secret structure from AWS."""
    secrets = get_aws_secrets()
    if not secrets:
        st.error("❌ Database connection failed: Could not load secrets from AWS.")
        return None
    
    try:
        db_params = {
            'host': secrets['DB_HOST'],
            'database': secrets['DB_DATABASE'],
            'user': secrets['DB_USER'],
            'password': secrets['DB_PASSWORD']
        }
        conn = mysql.connector.connect(**db_params)
        return conn
    except KeyError as e:
        st.error(f"❌ Database connection error: The key {e} is missing from your AWS secret.")
        st.error("Please ensure DB_HOST, DB_DATABASE, DB_USER, and DB_PASSWORD are all in your secret.")
        return None
    except mysql.connector.Error as err:
        st.error(f"❌ Database connection error: {err}")
        return None

@st.cache_data(ttl=600)
def fetch_organization_data(_user_email):
    """Fetches and aggregates latest survey data for a user's organization."""
    conn = get_db_connection()
    if not conn: return None, None, None

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (_user_email,))
        user_org_info = cursor.fetchone()
        if not user_org_info or not user_org_info.get('organisation_name'):
            st.warning(f"User '{_user_email}' not found or has no organization assigned.")
            return None, None, None
        
        org_name = user_org_info['organisation_name']
        org_data = {'Organization_Name': org_name}
        
        cursor.execute("SELECT DISTINCT admin_email FROM admin_team_members WHERE organisation_name = %s LIMIT 1", (org_name,))
        admin_info = cursor.fetchone()
        admin_email_for_org = admin_info.get('admin_email') if admin_info else None

        cursor.execute("SELECT Email_Id FROM user_registration WHERE organisation_name = %s", (org_name,))
        org_emails = [row['Email_Id'] for row in cursor.fetchall() if row.get('Email_Id')]
        if not org_emails:
            return org_data, org_name, admin_email_for_org

        tables_and_db_cols = {
            "Leadership": ["Leadership_avg", "Leadership_StrategicPlanning", "Leadership_ExternalEnvironment", "Leadership_Resources", "Leadership_Governance"],
            "Empower": ["Empower_avg", "Empower_Feedback", "Empower_ManagingRisk", "Empower_DecisionMaking", "Empower_RecoverySystems"],
            "Sustainability": ["Sustainability_avg", "Sustainability_LongTermPlanning", "Sustainability_ResourceManagement", "Sustainability_EnvironmentalImpact", "Sustainability_StakeholderEngagement"],
            "CulturePulse": ["CulturePulse_avg", "CulturePulse_Values", "CulturePulse_Respect", "CulturePulse_Communication", "CulturePulse_Diversity"],
            "Bonding": ["Bonding_avg", "Bonding_PersonalGrowth", "Bonding_Negotiation", "Bonding_GroupCohesion", "Bonding_Support"],
            "Influencers": ["Influencers_avg", "Influencers_Funders", "Influencers_Sponsors", "Influencers_PeerGroups", "Influencers_ExternalAlliances"]
        }
        all_latest_user_data = []
        placeholders = ','.join(['%s'] * len(org_emails))

        for table, cols in tables_and_db_cols.items():
            cols_str = ", ".join([f"`{c}`" for c in cols])
            query = f"""
                SELECT {cols_str} FROM (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY `Email_Id` ORDER BY `submission_id` DESC) as rn
                    FROM `{table}` WHERE `Email_Id` IN ({placeholders})
                ) ranked_data WHERE rn = 1;
            """
            cursor.execute(query, tuple(org_emails))
            all_latest_user_data.extend(cursor.fetchall())

        if not all_latest_user_data:
            return org_data, org_name, admin_email_for_org

        df_combined = pd.DataFrame(all_latest_user_data).apply(pd.to_numeric, errors='coerce')
        org_data.update(df_combined.mean().round(2).to_dict())
        return org_data, org_name, admin_email_for_org
    except Exception as e:
        st.error(f"❌ An unexpected error occurred during data fetching: {e}")
        return None, None, None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def get_color_for_score(score):
    """Returns a color hex code based on the score tier for consistency."""
    try:
        score = float(score)
        if score <= 3.0: return '#d62728'  # Sub Par (Red)
        elif score <= 5.0: return '#ff7f0e'  # Decent (Orange)
        else: return '#2ca02c'  # Top Tier (Green)
    except (ValueError, TypeError): return '#808080'

# -------------------- Plot & Display Functions --------------------
def plot_category_scores(scores_data, categories, benchmark=5.5):
    """Generates a bar chart for overall category scores."""
    scores = {cat: float(scores_data.get(f"{cat}_avg", 0.0)) for cat in categories}
    filtered_scores = {k: v for k, v in scores.items() if v > 0}
    if not filtered_scores:
        st.info("No overall category data available to plot.")
        return
    
    values = list(filtered_scores.values())
    colors = [get_color_for_score(v) for v in values]
    fig = go.Figure(go.Bar(x=list(filtered_scores.keys()), y=values, marker_color=colors, text=[f'{v:.2f}' for v in values], textposition='outside', textfont_color='white'))
    fig.add_shape(type="line", x0=-0.5, y0=benchmark, x1=len(filtered_scores)-0.5, y1=benchmark, line=dict(color="white", dash="dash", width=2))
    
    # REVERTED PLOT THEME: Switched back to dark theme for plots
    fig.update_layout(
        title_text="Overall Performance Across Elements",
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='#1a1a1a', 
        font_color='white',
        yaxis=dict(tickfont_color='white'),
        xaxis=dict(tickfont_color='white')
    )
    st.plotly_chart(fig, width='stretch')

def plot_sub_variable_donut_charts(scores_data, category, sub_vars):
    """Generates donut charts for sub-variables."""
    sub_scores = [{"name": sub, "score": float(scores_data.get(f"{category}_{sub}", 0.0))} for sub in sub_vars]
    sub_scores_to_plot = [s for s in sub_scores if s["score"] > 0]
    if not sub_scores_to_plot:
        st.info(f"No sub-variable data available for {category}.")
        return

    cols = st.columns(len(sub_scores_to_plot))
    for i, sub_data in enumerate(sub_scores_to_plot):
        with cols[i]:
            score = sub_data["score"]
            fig = go.Figure(go.Pie(values=[score, 7.0 - score], hole=.7, marker_colors=[get_color_for_score(score), '#444444'], sort=False, textinfo='none'))
            
            # REVERTED PLOT THEME: Switched back to dark theme for plots
            fig.update_layout(
                title_text=sub_data["name"],
                annotations=[dict(text=f'{score:.2f}', x=0.5, y=0.5, font_size=20, showarrow=False, font_color='white')],
                showlegend=False, height=250, paper_bgcolor='rgba(0,0,0,0)', font_color='white'
            )
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

def display_sub_category_performance_table(org_data, sub_vars_map, perf_type):
    """Displays a styled table of best/worst performing sub-categories."""
    all_scores = []
    for main_cat, sub_vars in sub_vars_map.items():
        for sub in sub_vars:
            score = org_data.get(f"{main_cat}_{sub}", 0.0)
            if float(score) > 0: all_scores.append({"Sub-Category": f"{main_cat} - {sub}", "Score": float(score)})
    if not all_scores:
        st.info(f"No data available to show {perf_type.lower()} performers.")
        return None, None

    df_all = pd.DataFrame(all_scores)
    df_display = df_all.sort_values(by="Score", ascending=(perf_type=="Worst")).head(5)
    styled_df = df_display.style.applymap(lambda s: f'background-color: {get_color_for_score(s)}; color: white;', subset=['Score'])
    return styled_df, df_display

def display_insight_text(df_best, df_worst, benchmark):
    """Generates and displays concise strength and focus area text."""
    if df_best is not None and not df_best.empty:
        top_strength = df_best.iloc[0]
        strengths_text = f"The top organizational strength is **{top_strength['Sub-Category']}** (Score: {top_strength['Score']:.1f}). This area significantly exceeds the benchmark, indicating a core competency that can be leveraged for broader strategic advantage."
        st.markdown(f"<div class='insight-section-container'><h3><span class='strength-icon'>✅</span> Strengths</h3><p>{strengths_text}</p></div>", unsafe_allow_html=True)

    if df_worst is not None and not df_worst.empty:
        top_focus = df_worst.iloc[0]
        focus_text = f"The primary area for focus is **{top_focus['Sub-Category']}** (Score: {top_focus['Score']:.1f}). Prioritizing improvements here could provide the greatest return, helping to lift overall performance and address potential vulnerabilities."
        st.markdown(f"<div class='insight-section-container' style='margin-top: 30px;'><h3><span class='focus-icon'>🎯</span> Areas for Focus</h3><p>{focus_text}</p></div>", unsafe_allow_html=True)

# -------------------- Email Functions --------------------
def send_email_with_attachment(recipient_email, subject, body_text):
    """Sends an email using a flat secret structure from AWS Secrets Manager."""
    secrets = get_aws_secrets()
    if not secrets:
        st.error("Email failed: Could not load secrets from AWS.")
        return False
    try:
        sender_email = secrets["SENDER_EMAIL"]
        sender_password = secrets["SENDER_APP_PASSWORD"]
        smtp_server = secrets["SMTP_SERVER"]
        smtp_port = int(secrets["SMTP_PORT"])
    except KeyError as e:
        st.error(f"Email failed: The key {e} is missing from your AWS secret.")
        st.error("Please ensure SENDER_EMAIL, SENDER_APP_PASSWORD, etc., are in your secret.")
        return False

    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = sender_email, recipient_email, subject
    msg.attach(MIMEText(body_text, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email sending failed: {e}")
        return False

def format_results_for_email(org_data, sub_vars_map, benchmark):
    """Formats performance data into a readable text string for email."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    body = f"Organizational Performance Report\nOrganization: {org_data.get('Organization_Name', 'N/A')}\nDate: {date_str}\nBenchmark: {benchmark}\n\n--- Overall Performance ---\n"
    for cat in sub_vars_map: body += f"- {cat}: {org_data.get(f'{cat}_avg', 'N/A')}\n"
    body += "\n--- Detailed Scores ---\n"
    for main_cat, sub_vars in sub_vars_map.items():
        body += f"\n>> {main_cat}\n"
        for sub in sub_vars: body += f"   - {sub}: {org_data.get(f'{main_cat}_{sub}', 'N/A')}\n"
    return body

# -------------------- Main Dashboard ------------------
def dashboard(navigate_to, user_email, **kwargs):
    """Renders the main dashboard page."""
    set_background(BG_IMAGE_PATH)

    org_data_key = f"org_data_{user_email}"
    if org_data_key not in st.session_state:
        with st.spinner("Fetching organization data..."):
            st.session_state[org_data_key] = fetch_organization_data(user_email)

    org_data, org_name, admin_email = st.session_state.get(org_data_key, (None, None, None))
    if not org_data:
        st.warning("Organization data could not be loaded."); st.button("Retry") and st.rerun()
        return

    st.session_state['org_name_for_header'] = org_name
    display_header_with_logo_and_text("Organisational Performance Dashboard", LOGO_PATH, org_name)

    sub_vars_map = {
        "Leadership": ["StrategicPlanning", "ExternalEnvironment", "Resources", "Governance"], "Empower": ["Feedback", "ManagingRisk", "DecisionMaking", "RecoverySystems"],
        "Sustainability": ["LongTermPlanning", "ResourceManagement", "EnvironmentalImpact", "StakeholderEngagement"], "CulturePulse": ["Values", "Respect", "Communication", "Diversity"],
        "Bonding": ["PersonalGrowth", "Negotiation", "GroupCohesion", "Support"], "Influencers": ["Funders", "Sponsors", "PeerGroups", "ExternalAlliances"]
    }
    benchmark = 5.5
    col1, col2 = st.columns([2, 1.2])

    with col1:
        # REVERTED: Removed the white container markdown wrappers
        plot_category_scores(org_data, sub_vars_map.keys(), benchmark=benchmark)
        
        st.subheader("Detailed Sub-Element Analysis")
        category = st.selectbox("Select Element", list(sub_vars_map.keys()), label_visibility="collapsed")
        plot_sub_variable_donut_charts(org_data, category, sub_vars_map[category])
        
    with col2:
        st.subheader("Score Tiers & Benchmark")
        st.markdown(f"**Benchmark** = `{benchmark}`")
        st.markdown("""<div class="score-tiers-container"><div><div style="width:20px;height:20px;background-color:#d62728;border-radius:3px;"></div><b>Sub Par</b></div><div><div style="width:20px;height:20px;background-color:#ff7f0e;border-radius:3px;"></div><b>Decent</b></div><div><div style="width:20px;height:20px;background-color:#2ca02c;border-radius:3px;"></div><b>Top Tier</b></div></div>""", unsafe_allow_html=True)

        st.subheader("Performance Highlights")
        perf_type = st.selectbox("View", ("Best", "Worst"), key="perf_table_select")
        styled_df, raw_df = display_sub_category_performance_table(org_data, sub_vars_map, perf_type)
        if styled_df is not None: st.dataframe(styled_df, width='stretch', hide_index=True)

        st.subheader("Actions")
        if admin_email:
            if st.button("📄 Email Full Results to Admin", width='stretch'):
                body = format_results_for_email(org_data, sub_vars_map, benchmark)
                if send_email_with_attachment(admin_email, f"{org_name} Performance Report", body): st.success("Email sent!")
        else: st.info("Admin email not found.")

        st.subheader("Explore VClarifi Agents")
        nav_cols = st.columns(2)
        with nav_cols[0]:
            if st.button("➡ Recommendations", width='stretch'): navigate_to("Recommendations")
            if st.button("➡ DocBot", width='stretch'): navigate_to("docbot")
        with nav_cols[1]:
            if st.button("➡ VClarifi Agent", width='stretch'): navigate_to("VClarifi_Agent")
            if st.button("➡ Text-to-Video", width='stretch'): navigate_to("text_2_video_agent")


    _, df_best = display_sub_category_performance_table(org_data, sub_vars_map, "Best")
    _, df_worst = display_sub_category_performance_table(org_data, sub_vars_map, "Worst")
    display_insight_text(df_best, df_worst, benchmark)

def placeholder_page(title, navigate_to, **kwargs):
    set_background(BG_IMAGE_PATH)
    display_header_with_logo_and_text(title, LOGO_PATH, st.session_state.get('org_name_for_header', "Organization"))
    st.info(f"The '{title.strip()}' feature is under construction.")
    if st.button("⬅ Back to Dashboard"): navigate_to("Dashboard")

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="VClarifi Dashboard")
    if 'page' not in st.session_state: st.session_state.page = 'Dashboard'
    if 'user_email' not in st.session_state: st.session_state.user_email = 'admin_alpha@example.com'

    def nav_to(page_name): st.session_state.page = page_name; st.rerun()
    
    page_map = {
        "Dashboard": lambda: dashboard(navigate_to=nav_to, user_email=st.session_state.user_email),
        "Recommendations": lambda: placeholder_page("Recommendations", nav_to),
        "VClarifi_Agent": lambda: placeholder_page("VClarifi Agent", nav_to),
        "docbot": lambda: placeholder_page("DocBot", nav_to),
        "text_2_video_agent": lambda: placeholder_page("Text-to-Video", nav_to),
    }
    
    page_func = page_map.get(st.session_state.page)
    if page_func:
        page_func()
    else:
        st.error("Page not found.")
        st.session_state.page = 'Dashboard'
        if st.button("Go to Dashboard"):
            st.rerun()
