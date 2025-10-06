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

# Set up basic logging (optional, but good practice)
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
BG_IMAGE_PATH = "images/background.jpg"
LOGO_IMAGE_PATH = "images/VTARA.png"
# 🚨 CORRECTED: Use the correct model name without the 'models/' prefix
GEMINI_MODEL = "gemini-1.5-flash" 

# --- AWS Secrets Manager Configuration (REQUIRED TO BE CORRECT) ---
# 🚨 CUSTOMIZED: Set the name of your secret in AWS Secrets Manager
SECRET_NAME = "production/vclarifi/secrets" 
# 🚨 CUSTOMIZED: Set the region where your secret is stored
REGION_NAME = "us-east-1" 

# --- PAGE CONFIGURATION ---
# This must be the first Streamlit command in your script
st.set_page_config(
    page_title="Vclarifi",
    page_icon="images/VTARA.png",
    layout="wide"
)

# --- Survey Questions Dictionary (Retained) ---
SURVEY_QUESTIONS = {
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


# ==============================================================================
# --- CRITICAL FIX: Secrets Manager (Uses Boto3 to fetch from AWS) ---
# ==============================================================================
@st.cache_data(show_spinner="Connecting to AWS Secrets Manager...")
def get_application_secrets(secret_name, region_name):
    """
    Fetches and parses the secret from AWS Secrets Manager using boto3.
    """
    try:
        # Create a Secrets Manager client
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )

        # Attempt to retrieve the secret value
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )

    except ClientError as e:
        # Handle exceptions that may occur during the API call
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            st.error(f"❌ Secret not found: {secret_name}. Check the Secret Name and Region.")
        elif e.response['Error']['Code'] == 'AccessDeniedException':
            st.error("❌ Access Denied. Check IAM permissions for 'secretsmanager:GetSecretValue'.")
        elif e.response['Error']['Code'] == 'DecryptionFailureException':
            st.error("❌ Secret decryption failed. Check KMS key permissions.")
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            st.error("❌ AWS internal service error.")
        else:
            st.error(f"❌ AWS Secrets Manager Error: {e}")
        return None
    except Exception as e:
        st.error(f"❌ General Boto3/AWS Connection Error: Ensure Boto3 is installed and AWS credentials are set up: {e}")
        return None

    # The secret value is a JSON string which needs to be parsed
    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
        try:
            secrets_dict = json.loads(secret)
            
            # Perform basic validation on the expected keys
            required_keys = ["GEMINI_API_KEY", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_DATABASE"]
            if not all(k in secrets_dict for k in required_keys):
                st.error("❌ Secret JSON is missing one or more required keys: GEMINI_API_KEY, DB_HOST, etc. Check the secret's content.")
                return None
            
            return secrets_dict
            
        except json.JSONDecodeError:
            st.error("❌ Could not parse the SecretString as JSON. Is the secret stored as a valid JSON string?")
            return None
    
    st.error("❌ Secret found but neither SecretString nor SecretBinary were populated.")
    return None

# ==============================================================================
# --- UTILITY FUNCTIONS (Retained) ---
# ==============================================================================

def encode_image_to_base64(image_path):
    """Encodes an image file to a base64 string."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""
    except Exception as e:
        st.error(f"Error encoding image {image_path}: {e}")
        return ""
        
def set_page_style(bg_image_path):
    """Sets the background image and custom styles for the page."""
    encoded_bg = encode_image_to_base64(bg_image_path)
    
    background_style = f"""
        background-image: url("data:image/jpg;base64,{encoded_bg}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    """ if encoded_bg else "background-color: #0F172A;"

    st.markdown(f"""
        <style>
        /* --- Main Page Styling --- */
        [data-testid="stAppViewContainer"] {{
            {background_style}
        }}
        [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}

        /* --- Main Content Area --- */
        .main .block-container {{
            background-color: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 2rem;
            border-radius: 16px;
        }}

        /* --- Typography --- */
        h1, h2, h3, h4, h5, h6 {{ color: #FFFFFF !important; }}
        .stMarkdown p {{ color: #CBD5E1; }}

        /* --- Page Header Container --- */
        .page-header-container {{
            background-color: rgba(26, 32, 44, 0.7);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            margin-bottom: 2rem;
        }}
        .page-header-container h1 {{
            margin-bottom: 0.5rem;
            font-size: 2.5rem; 
        }}
        .page-header-container h3 {{
            margin-top: 0;
            color: #A0AEC0 !important; 
            font-weight: 400;
        }}

        /* --- Category Card Styling --- */
        .category-card-box {{
            background: linear-gradient(145deg, #2D3748, #1A202C);
            border: 1px solid #4A5568;
            border-radius: 16px;
            padding: 1.5rem 1.5rem 1rem 1.5rem;
            text-align: center;
            transition: all 0.3s ease-in-out;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        }}
        .category-card-box:hover {{
            transform: translateY(-8px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
            border-color: #718096;
        }}
        .category-card-box h3 {{
            font-size: 1.75rem;
            margin: 0.5rem 0;
            color: #FFFFFF;
        }}
        .category-card-box p {{
            font-size: 1rem;
            color: #A0AEC0;
            margin: 0.25rem 0;
        }}
        
        /* --- Button below the card --- */
        .stButton > button {{
            font-weight: bold;
            border-radius: 8px;
            transition: all 0.2s ease-in-out;
            width: 100%;
        }}
        .category-card-box + div[data-testid="stButton"] > button {{
            background-color: #4A5568;
            color: #F7FAFC;
            border: none;
            padding: 0.75rem 0;
        }}
        .category-card-box + div[data-testid="stButton"] > button:hover {{
            background-color: #718096;
            color: white;
        }}

        /* --- Recommendation Container Styling --- */
        .recommendation-container {{
            background-color: #1A202C;
            border: 1px solid #4A5568;
            border-radius: 12px;
            padding: 2rem;
            margin-top: 1.5rem;
        }}
        .recommendation-container h3, .recommendation-container h4 {{
            color: #FFFFFF !important;
            border-bottom: 2px solid #4A5568;
            padding-bottom: 0.5rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
        }}
        .recommendation-container p,
        .recommendation-container li,
        .recommendation-container strong {{
            color: #FFFFFF !important;
            font-size: 1.15rem !important;
            line-height: 1.7 !important;
        }}
        
        /* --- Score Indicator Styling --- */
        .score-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            vertical-align: middle;
        }}
        .score-low {{ background-color: #E53E3E; box-shadow: 0 0 10px #E53E3E; }}
        .score-medium {{ background-color: #DD6B20; box-shadow: 0 0 10px #DD6B20; }}
        .score-high {{ background-color: #38A169; box-shadow: 0 0 10px #38A169; }}
        </style>
    """, unsafe_allow_html=True)

def display_logo_and_text(logo_path, org_name):
    """Displays a logo and organization name in the top right corner."""
    encoded_logo = encode_image_to_base64(logo_path)
    org_display = f"<div style='font-size: 1.2rem; font-weight: bold; color: white; text-shadow: 1px 1px 2px black;'>{org_name if org_name else 'Organization'}</div>" if org_name else ""

    if encoded_logo or org_display:
        st.markdown(f"""
            <div style='position: fixed; top: 15px; right: 20px; display: flex; align-items: center; gap: 10px; z-index: 1000; padding: 8px; background-color: rgba(0,0,0,0.5); border-radius: 10px;'>
                {f'<img src="data:image/png;base64,{encoded_logo}" style="width: 60px;">' if encoded_logo else ''}
                {org_display}
            </div>
        """, unsafe_allow_html=True)

def get_score_indicator_html(score):
    """Returns an HTML span for a color-coded score indicator."""
    if score <= 3.0:
        css_class = "score-low"
        tier = "Needs Focus"
    elif score <= 5.0:
        css_class = "score-medium"
        tier = "Potential"
    else:
        css_class = "score-high"
        tier = "Strength"
    return f"<span class='score-indicator {css_class}'></span> {tier}"


# ==============================================================================
# --- DATA ACCESS (Uses Boto3-based secret getter) ---
# ==============================================================================

@st.cache_data
def fetch_organization_data(user_email):
    """Fetches organization data using credentials from the secret store."""
    
    # Use the Boto3 function to get the actual secrets
    secrets = get_application_secrets(SECRET_NAME, REGION_NAME) 
    
    if not secrets:
        st.info("Cannot proceed without valid secrets.")
        return None, None
    
    conn = None
    try:
        # DB credentials retrieved from the parsed secret
        db_params = {
            'host': secrets['DB_HOST'],
            'database': secrets['DB_DATABASE'],
            'user': secrets['DB_USER'],
            'password': secrets['DB_PASSWORD']
        }
        
        # MOCK Data for demonstration if DB connection is not possible
        if db_params['host'] == 'your_db_host':
            org_name = "Mock Organization Alpha"
            # Simulate a successful data fetch
            org_data = {
                'Organization_Name': org_name,
                "Leadership_avg": 3.5,
                "Influencers_avg": 6.1,
                "Bonding_avg": 4.8,
                "CulturePulse_avg": 2.9,
                "Sustainability_avg": 5.5,
                "Empower_avg": 4.1
            }
            return org_data, org_name
        
        # --- LIVE DB LOGIC ---
        conn = mysql.connector.connect(**db_params)
        cursor = conn.cursor(dictionary=True)
        # 1. Fetch Organization Name
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (user_email,))
        user_org_info = cursor.fetchone()
        if not user_org_info or not user_org_info.get('organisation_name'):
            st.warning(f"User '{user_email}' not found or has no organization assigned.")
            return None, None
        org_name = user_org_info['organisation_name']
        
        # 2. Fetch all user emails for the organization (Logic retained)
        cursor.execute("SELECT Email_Id FROM user_registration WHERE organisation_name = %s", (org_name,))
        org_emails = [row['Email_Id'] for row in cursor.fetchall()]

        # 3. Fetch latest averages for all users (Logic retained)
        avg_cols = ["Leadership_avg", "Influencers_avg", "Bonding_avg", "CulturePulse_avg", "Sustainability_avg", "Empower_avg"]
        placeholders = ','.join(['%s'] * len(org_emails))
        query = f"""
            SELECT {', '.join(avg_cols)}
            FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY Email_ID ORDER BY id DESC) as rn
                FROM Averages
                WHERE Email_ID IN ({placeholders})
            ) ranked_data
            WHERE rn = 1;
        """
        cursor.execute(query, tuple(org_emails))
        all_latest_user_data = cursor.fetchall()

        if not all_latest_user_data:
            st.warning(f"No survey data found for organization '{org_name}' in the Averages table.")
            return None, org_name
            
        df_combined = pd.DataFrame(all_latest_user_data)
        for col in avg_cols:
             if col in df_combined.columns:
                 df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce')

        if df_combined[avg_cols].isnull().all().all():
            st.warning(f"Found submissions for '{org_name}', but all average score columns are empty/non-numeric.")
            return None, org_name
            
        org_averages = df_combined.mean(numeric_only=True).to_dict()
        org_data = {'Organization_Name': org_name, **org_averages}
        return org_data, org_name
    except KeyError as e:
        st.error(f"❌ Database error: A required key is missing from the AWS secret: {e}")
        return None, None
    except Error as err:
        st.error(f"❌ Database connection error: {err}")
        return None, None
    finally:
        if conn and conn.is_connected():
            conn.close()

# ==============================================================================
# --- Recommendation Generation (Uses new secret getter and corrected model) ---
# ==============================================================================

@st.cache_data(show_spinner=False)
def generate_recommendations(_category_name, average_score, questions_context):
    """Generates recommendations using the Gemini API."""
    
    # 1. Fetch API Key
    gemini_api_key = None
    try:
        # Use the Boto3 function to get the actual secrets
        all_secrets = get_application_secrets(SECRET_NAME, REGION_NAME) 
        
        if not all_secrets:
            return "Sorry, we were unable to generate recommendations at this time (Secret Fetch Error)."
            
        gemini_api_key = all_secrets.get("GEMINI_API_KEY")
        
        if not gemini_api_key:
            st.error("API key configuration error: 'GEMINI_API_KEY' not found in the AWS secret.")
            return "Sorry, we were unable to generate recommendations due to a configuration error (API Key Missing)."
            
    except Exception as e:
        st.error(f"An unexpected error occurred while fetching secrets for Gemini: {e}")
        return "Sorry, we were unable to generate recommendations at this time. (Secret Fetch Error)"
    
    # 2. Configure and Generate Content
    try:
        genai.configure(api_key=gemini_api_key)
        # Uses the corrected GEMINI_MODEL = "gemini-1.5-flash"
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        
        category_questions = questions_context.get(_category_name, {})
        question_details = "\n".join([f"- **{sub_cat}:** {question}" for sub_cat, question in category_questions.items()])
        
        prompt = (
            f"As an expert consultant for high-performance sports organizations, analyze the following and provide specific, actionable recommendations.\n\n"
            f"**Category:** '{_category_name}'\n"
            f"**Organization's Average Score:** {average_score:.2f} (on a 1-7 scale).\n\n"
            f"This score is based on these key questions:\n{question_details}\n\n"
            f"**Task:**\n"
            f"Given the score of **{average_score:.2f}**, provide practical strategies to improve performance in '{_category_name}'. "
            f"Structure your response with clear, actionable steps for leadership and the team. Focus on tangible outcomes and how to measure improvement. Use markdown formatting (bolding, bullets).\n\n"
            f"**IMPORTANT:** Do not add a main title or heading to your response (e.g., do not write 'Action Plan for...'). Begin the response directly with the actionable steps or sub-headings."
        )
        
        response = model.generate_content(prompt)
        return getattr(response, "text", "Could not generate text response from the model.")
        
    except Exception as e:
        # Catch errors specifically from the API call (e.g., invalid key, rate limit)
        st.error(f"An error occurred during Gemini API call for {_category_name}: {e}")
        return "Sorry, we were unable to generate recommendations at this time. (Gemini API Call Failed)"

# ==============================================================================
# --- UI RENDERING FUNCTIONS (Retained) ---
# ==============================================================================

def display_category_grid(category_scores, navigate_to):
    """Displays a grid of clickable category cards."""
    st.subheader("Performance Categories")
    st.markdown("Click on a category to view detailed, AI-powered recommendations.")
    st.write("") 
    
    # Sort by score (lowest first) to prioritize areas needing focus
    sorted_categories = sorted(category_scores.items(), key=lambda item: item[1])
    
    for i in range(0, len(sorted_categories), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(sorted_categories):
                category, score = sorted_categories[i+j]
                with cols[j]:
                    indicator_html = get_score_indicator_html(score)
                    
                    st.markdown(f"""
                        <div class="category-card-box">
                            <div>
                                <h3>{category}</h3>
                                <p>{indicator_html}</p>
                                <p>Score: {score:.2f} / 7</p>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("View Recommendations", key=f"btn_{category}"):
                        st.session_state.selected_category = category
                        st.rerun()
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("⬅️ Back to Main Dashboard"):
        if navigate_to:
            navigate_to("Dashboard")

def display_recommendation_detail(category, score):
    """Displays the detailed recommendations for a single selected category."""
    if st.button("⬅️ Back to All Categories"):
        st.session_state.selected_category = None
        st.rerun()

    indicator_html = get_score_indicator_html(score)
    st.markdown(f"## Recommendations for {category}")
    st.markdown(f"Current Performance: **{indicator_html}** (Score: {score:.2f} / 7)", unsafe_allow_html=True)
    
    with st.spinner(f"Generating tailored recommendations for {category}..."):
        recommendations_text = generate_recommendations(category, score, SURVEY_QUESTIONS) 
        st.markdown(f"""
            <div class="recommendation-container">
            {recommendations_text}
            </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# --- MAIN PAGE FUNCTION (Retained) ---
# ==============================================================================

def recommendations_page(navigate_to=None, user_email=None, **kwargs):
    """Renders the main recommendations page."""
    set_page_style(BG_IMAGE_PATH) 
    
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = None

    org_data, org_name = fetch_organization_data(user_email)
    display_logo_and_text(LOGO_IMAGE_PATH, org_name)

    st.markdown(f"""
            <div class="page-header-container">
                <h1>Performance Enhancement Recommendations</h1>
                <h3>For {org_name or 'Your Organization'}</h3>
            </div>
    """, unsafe_allow_html=True)

    if org_data is None:
        st.info("Waiting for organization data to be loaded or no data available. Check the error messages above for secret fetching issues.")
        if st.button("⬅️ Back to Dashboard"):
            if navigate_to: navigate_to("Dashboard")
        return

    category_avg_keys = {
        "Leadership": "Leadership_avg", "Empower": "Empower_avg", "Sustainability": "Sustainability_avg",
        "CulturePulse": "CulturePulse_avg", "Bonding": "Bonding_avg", "Influencers": "Influencers_avg"
    }
    
    # Filter for valid scores
    category_scores = {
        cat: org_data[key] for cat, key in category_avg_keys.items() 
        if key in org_data and pd.notna(org_data[key])
    }

    if not category_scores:
        st.warning(f"No valid average category scores were found for organization '{org_name}'.")
        if st.button("⬅️ Back to Dashboard"):
            if navigate_to: navigate_to("Dashboard")
        return

    if st.session_state.selected_category is None:
        display_category_grid(category_scores, navigate_to)
    else:
        selected_cat = st.session_state.selected_category
        score = category_scores[selected_cat]
        display_recommendation_detail(selected_cat, score)

# --- Example Usage (Retained) ---
if __name__ == "__main__":
    
    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = 'admin_alpha@example.com' # Example user email for testing
    
    if 'page' not in st.session_state:
        st.session_state['page'] = 'Recommendations'

    def nav_to(page):
        st.session_state['page'] = page
        if 'selected_category' in st.session_state:
            del st.session_state['selected_category']
        st.rerun()

    if st.session_state.get('page') == 'Recommendations':
        recommendations_page(nav_to, st.session_state.user_email)
    elif st.session_state.get('page') == 'Dashboard':
        set_page_style(BG_IMAGE_PATH)
        st.title("Dashboard Placeholder")
        st.write("This is the main dashboard.")
        if st.button("Go to Recommendations"):
            nav_to("Recommendations")
