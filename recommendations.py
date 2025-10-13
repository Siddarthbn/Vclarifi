import os
import base64
import pandas as pd
import streamlit as st
import mysql.connector
from mysql.connector import Error
import google.generativeai as genai
import logging
import boto3
import json
from botocore.exceptions import ClientError

# Set up basic logging
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"
GEMINI_MODEL = "gemini-2.5-flash" 

# --- AWS Secrets Manager Configuration ---
SECRET_NAME = "production/vclarifi/secrets"
REGION_NAME = "us-east-1"

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Vclarifi Recommendations",
    page_icon="images/VTARA.png",
    layout="wide"
)

# --- REFINED: Detailed AACS Survey Questions ---
AACS_SURVEY_QUESTIONS = {
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

# ==============================================================================
# --- AWS Secrets Manager ---
# ==============================================================================
@st.cache_data(show_spinner="Connecting to AWS Secrets Manager...")
def get_application_secrets(secret_name, region_name):
    """Fetches and parses the secret from AWS Secrets Manager using boto3."""
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            st.error(f"❌ Secret not found: {secret_name}. Check the Secret Name and Region.")
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            st.error("❌ Access Denied. Check IAM permissions for 'secretsmanager:GetSecretValue'.")
        else:
            st.error(f"❌ AWS Secrets Manager Error: {e}")
        return None
    except Exception as e:
        st.error(f"❌ General Boto3/AWS Connection Error: {e}")
        return None

    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
        try:
            secrets_dict = json.loads(secret)
            required_keys = ["GEMINI_API_KEY", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_DATABASE"]
            if not all(k in secrets_dict for k in required_keys):
                st.error("❌ Secret JSON is missing required keys. Check the secret's content.")
                return None
            return secrets_dict
        except json.JSONDecodeError:
            st.error("❌ Could not parse the SecretString as JSON.")
            return None
    st.error("❌ Secret found but no SecretString was populated.")
    return None

# ==============================================================================
# --- UTILITY & STYLING FUNCTIONS ---
# ==============================================================================

def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string for embedding in HTML/CSS."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

def set_page_style(bg_image_path):
    """Sets the background image and custom CSS styles for the page."""
    encoded_bg = encode_image_to_base64(bg_image_path)
    background_style = f'background-image: url("data:image/jpg;base64,{encoded_bg}"); background-size: cover; background-position: center; background-attachment: fixed;' if encoded_bg else "background-color: #0F172A;"
    st.markdown(f"""<style>
        [data-testid="stAppViewContainer"] {{ {background_style} }}
        [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
        .main .block-container {{ background-color: rgba(15, 23, 42, 0.85); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); padding: 2rem; border-radius: 16px; }}
        h1, h2, h3, h4, h5, h6 {{ color: #FFFFFF !important; }}
        .stMarkdown p {{ color: #CBD5E1; }}
        .page-header-container {{ background-color: rgba(26, 32, 44, 0.7); border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 2rem; }}
        .page-header-container h1 {{ margin-bottom: 0.5rem; font-size: 2.5rem; }}
        .page-header-container h3 {{ margin-top: 0; color: #A0AEC0 !important; font-weight: 400; }}
        .category-card-box {{ background: linear-gradient(145deg, #2D3748, #1A202C); border: 1px solid #4A5568; border-radius: 16px; padding: 1.5rem 1.5rem 1rem 1.5rem; text-align: center; transition: all 0.3s ease-in-out; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2); }}
        .category-card-box:hover {{ transform: translateY(-8px); box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3); border-color: #718096; }}
        .category-card-box h3 {{ font-size: 1.75rem; margin: 0.5rem 0; color: #FFFFFF; }}
        .category-card-box p {{ font-size: 1rem; color: #A0AEC0; margin: 0.25rem 0; }}
        .stButton > button {{ font-weight: bold; border-radius: 8px; transition: all 0.2s ease-in-out; width: 100%; }}
        .category-card-box + div[data-testid="stButton"] > button {{ background-color: #4A5568; color: #F7FAFC; border: none; padding: 0.75rem 0; }}
        .category-card-box + div[data-testid="stButton"] > button:hover {{ background-color: #718096; color: white; }}
        .recommendation-container {{ background-color: #1A202C; border: 1px solid #4A5568; border-radius: 12px; padding: 2rem; margin-top: 1.5rem; }}
        .recommendation-container h3, .recommendation-container h4 {{ color: #FFFFFF !important; border-bottom: 2px solid #4A5568; padding-bottom: 0.5rem; margin-top: 2rem; margin-bottom: 1rem; }}
        .recommendation-container p, .recommendation-container li, .recommendation-container strong {{ color: #FFFFFF !important; font-size: 1.15rem !important; line-height: 1.7 !important; }}
        .score-indicator {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }}
        .score-low {{ background-color: #E53E3E; box-shadow: 0 0 10px #E53E3E; }}
        .score-medium {{ background-color: #DD6B20; box-shadow: 0 0 10px #DD6B20; }}
        .score-high {{ background-color: #38A169; box-shadow: 0 0 10px #38A169; }}
        </style>""", unsafe_allow_html=True)

def display_logo_and_text(logo_path, org_name):
    """Displays a logo and organization name in the top right corner."""
    encoded_logo = encode_image_to_base64(logo_path)
    org_display = f"<div style='font-size: 1.2rem; font-weight: bold; color: white; text-shadow: 1px 1px 2px black;'>{org_name if org_name else 'Organization'}</div>" if org_name else ""
    if encoded_logo or org_display:
        st.markdown(f"""<div style='position: fixed; top: 15px; right: 20px; display: flex; align-items: center; gap: 10px; z-index: 1000; padding: 8px; background-color: rgba(0,0,0,0.5); border-radius: 10px;'>
            {f'<img src="data:image/png;base64,{encoded_logo}" style="width: 60px;">' if encoded_logo else ''}
            {org_display}</div>""", unsafe_allow_html=True)

def get_score_indicator_html(score):
    """Returns an HTML span for a color-coded score indicator based on a 0-100 scale."""
    if score < 50:
        css_class, tier = "score-low", "Needs Focus"
    elif score < 75:
        css_class, tier = "score-medium", "Potential"
    else:
        css_class, tier = "score-high", "Strength"
    return f"<span class='score-indicator {css_class}'></span> {tier}"

# ==============================================================================
# --- DATABASE & DATA FETCHING ---
# ==============================================================================

@st.cache_data
def fetch_aacs_team_scores(user_email):
    """Fetches the latest AACS scores for an entire organization and calculates the team average."""
    secrets = get_application_secrets(SECRET_NAME, REGION_NAME)
    if not secrets:
        st.info("Cannot proceed without valid secrets.")
        return None, None

    conn = None
    try:
        conn = mysql.connector.connect(
            host=secrets['DB_HOST'], database=secrets['DB_DATABASE'],
            user=secrets['DB_USER'], password=secrets['DB_PASSWORD']
        )
        cursor = conn.cursor(dictionary=True)

        # 1. Get user's organization name
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (user_email,))
        user_info = cursor.fetchone()
        if not user_info or not user_info.get('organisation_name'):
            st.warning(f"Could not find an organization for user: {user_email}")
            return None, None
        org_name = user_info['organisation_name']

        # 2. Get all team members in that organization
        cursor.execute("SELECT Email_Id FROM user_registration WHERE organisation_name = %s", (org_name,))
        team_emails = [row['Email_Id'] for row in cursor.fetchall()]
        if not team_emails:
            return None, org_name

        # 3. Get the latest completed submission ID for each team member
        placeholders = ','.join(['%s'] * len(team_emails))
        query_ids = f"""
            SELECT id FROM (
                SELECT id, Email_Id, ROW_NUMBER() OVER(PARTITION BY Email_Id ORDER BY completion_date DESC) as rn
                FROM submissions WHERE Email_Id IN ({placeholders}) AND status = 'completed'
            ) ranked_submissions WHERE rn = 1
        """
        cursor.execute(query_ids, tuple(team_emails))
        sub_ids = [row['id'] for row in cursor.fetchall()]
        if not sub_ids:
            st.warning(f"No completed submissions found for the organization '{org_name}'.")
            return None, org_name
        
        # 4. Fetch all AACS scores for these submissions
        score_placeholders = ', '.join(['%s'] * len(sub_ids))
        query_scores = f"""
            SELECT als.Alignment_score, ags.Agility_score, cs.Capability_score, ss.Sustainability_score
            FROM submissions s
            LEFT JOIN alignment_scores als ON s.id = als.submission_id
            LEFT JOIN agility_scores ags ON s.id = ags.submission_id
            LEFT JOIN capability_scores cs ON s.id = cs.submission_id
            LEFT JOIN sustainability_scores ss ON s.id = ss.submission_id
            WHERE s.id IN ({score_placeholders})
        """
        cursor.execute(query_scores, sub_ids)
        scores_data = cursor.fetchall()

        if not scores_data:
            return None, org_name

        # 5. Calculate team averages
        df_scores = pd.DataFrame(scores_data)
        team_avg_scores = df_scores.mean().to_dict()
        return team_avg_scores, org_name

    except Error as err:
        st.error(f"❌ Database error: {err}")
        return None, None
    finally:
        if conn and conn.is_connected():
            conn.close()

# ==============================================================================
# --- AI RECOMMENDATION ENGINE ---
# ==============================================================================

@st.cache_data(show_spinner=False)
def generate_recommendations(_category_name, average_score, survey_questions):
    """Generates recommendations using the Gemini API based on detailed AACS questions."""
    all_secrets = get_application_secrets(SECRET_NAME, REGION_NAME)
    if not all_secrets or not all_secrets.get("GEMINI_API_KEY"):
        st.error("API key configuration error. Could not generate recommendations.")
        return "Sorry, we were unable to generate recommendations due to a configuration error."
    
    try:
        genai.configure(api_key=all_secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        
        category_specific_questions = survey_questions.get(_category_name, {})
        question_details = "\n".join([f"- {q_text}" for q_id, q_text in category_specific_questions.items()])
        
        prompt = (
            f"As an expert consultant for high-performance teams, analyze the following and provide specific, actionable recommendations.\n\n"
            f"**Pillar:** '{_category_name}'\n"
            f"**Team's Average Score:** {average_score:.1f} (on a 0-100 scale).\n\n"
            f"This score is a reflection of the team's collective sentiment on key questions, including:\n{question_details}\n\n"
            f"**Task:**\n"
            f"Given the score of **{average_score:.1f}**, provide a strategic action plan to improve performance in the '{_category_name}' pillar. "
            f"Your recommendations should be practical and directly address the themes covered in the questions above. "
            f"For a low score, focus on foundational fixes. For a medium score, focus on optimization. For a high score, focus on advanced strategies and maintaining excellence. "
            f"Use markdown formatting (bolding, bullets).\n\n"
            f"**IMPORTANT:** Do not add a main title or heading to your response. Begin directly with your analysis and actionable steps."
        )
        
        response = model.generate_content(prompt)
        return getattr(response, "text", "Could not generate text response from the model.")
        
    except Exception as e:
        st.error(f"An error occurred during Gemini API call for {_category_name}: {e}")
        return "Sorry, we were unable to generate recommendations at this time."

# ==============================================================================
# --- UI RENDERING FUNCTIONS ---
# ==============================================================================

def display_category_grid(category_scores, navigate_to):
    """Displays a grid of clickable category cards for the 4 AACS pillars."""
    st.subheader("Performance Pillars")
    st.markdown("Click on a pillar to view detailed, AI-powered recommendations for your team.")
    st.write("")
    
    sorted_categories = sorted(category_scores.items(), key=lambda item: item[1])
    
    cols = st.columns(len(sorted_categories) if sorted_categories else 1)
    for i, (category, score) in enumerate(sorted_categories):
        with cols[i]:
            indicator_html = get_score_indicator_html(score)
            st.markdown(f"""<div class="category-card-box">
                <h3>{category}</h3>
                <p>{indicator_html}</p>
                <p>Score: {score:.1f} / 100</p>
            </div>""", unsafe_allow_html=True)
            if st.button("View Recommendations", key=f"btn_{category}"):
                st.session_state.selected_category = category
                st.rerun()

    st.markdown("<br><br><hr>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Main Dashboard"):
        if navigate_to: navigate_to("Dashboard")

def display_recommendation_detail(category, score):
    """Displays the detailed recommendations for a single selected category."""
    if st.button("⬅️ Back to All Pillars"):
        st.session_state.selected_category = None
        st.rerun()

    indicator_html = get_score_indicator_html(score)
    st.markdown(f"## Recommendations for {category}")
    st.markdown(f"Current Team Performance: **{indicator_html}** (Score: {score:.1f} / 100)", unsafe_allow_html=True)
    
    with st.spinner(f"Generating tailored recommendations for {category}..."):
        recommendations_text = generate_recommendations(category, score, AACS_SURVEY_QUESTIONS)
        st.markdown(f'<div class="recommendation-container">{recommendations_text}</div>', unsafe_allow_html=True)

# ==============================================================================
# --- MAIN PAGE FUNCTION ---
# ==============================================================================

def recommendations_page(navigate_to=None, user_email=None, **kwargs):
    """Renders the main recommendations page."""
    set_page_style(BG_IMAGE_PATH)
    
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None

    team_scores, org_name = fetch_aacs_team_scores(user_email)
    display_logo_and_text(LOGO_IMAGE_PATH, org_name)

    st.markdown(f"""
        <div class="page-header-container">
            <h1>Performance Enhancement Recommendations</h1>
            <h3>For {org_name or 'Your Team'}</h3>
        </div>""", unsafe_allow_html=True)

    if team_scores is None:
        st.info("Waiting for team AACS data to be loaded or no data is available. Check for error messages above.")
        if st.button("⬅️ Back to Dashboard"):
            if navigate_to: navigate_to("Dashboard")
        return

    aacs_category_keys = {
        "Alignment": "Alignment_score", "Agility": "Agility_score",
        "Capability": "Capability_score", "Sustainability": "Sustainability_score"
    }
    
    category_scores = {cat: team_scores[key] for cat, key in aacs_category_keys.items() if key in team_scores and pd.notna(team_scores[key])}

    if not category_scores:
        st.warning(f"No valid AACS scores were found for '{org_name}'. Please ensure team members have completed the survey.")
        if st.button("⬅️ Back to Dashboard"):
            if navigate_to: navigate_to("Dashboard")
        return

    if st.session_state.selected_category is None:
        display_category_grid(category_scores, navigate_to)
    else:
        selected_cat = st.session_state.selected_category
        score = category_scores[selected_cat]
        display_recommendation_detail(selected_cat, score)

# ==============================================================================
# --- SCRIPT EXECUTION ---
# ==============================================================================

if __name__ == "__main__":
    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = 'siddarth@vtaraenergygroup.com' 
    
    def mock_navigate_to(page):
        """A dummy navigation function for testing purposes."""
        st.success(f"Navigating to {page}...")

    recommendations_page(navigate_to=mock_navigate_to, user_email=st.session_state.user_email)
