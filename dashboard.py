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

# --- Paths to your images ---
LOGO_PATH = r"C:\Users\DELL\Videos\APP\VTARA.PNG"
BG_IMAGE_PATH = r"C:\Users\DELL\Videos\APP\bg.jpg"

# -------------------- UI Helpers --------------------
def encode_image(image_path):
    """Encodes an image to a base64 string for embedding in HTML."""
    if not os.path.exists(image_path):
        st.warning(f"DEBUG: File does not exist at path: {os.path.abspath(image_path)}. Please verify the file location.")
        return ""

    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Image not found at path: {image_path}. Please ensure the path is correct.")
        return ""
    except Exception as e:
        st.error(f"Error encoding image {image_path}: {e}")
        return ""

def set_background(image_path, default_color_hex="#438454"):
    """Sets the overall background as an image or a default color."""
    bg_style = ""
    if image_path and os.path.exists(image_path):
        encoded_image = encode_image(image_path)
        if encoded_image:
            # Determine mime type dynamically or assume based on common extensions
            lower_path = image_path.lower()
            if lower_path.endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            elif lower_path.endswith(".png"):
                mime_type = "image/png"
            else:
                mime_type = "application/octet-stream" # Fallback
                st.warning(f"Unsupported image extension for background: {image_path}. Using generic mime type.")

            bg_style = f"""
                background-image: url('data:{mime_type};base64,{encoded_image}');
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed; /* Keeps background fixed during scroll */
            """
        else:
            st.warning(f"Could not encode background image: {image_path}. Using fallback color.")
            bg_style = f"background-color: {default_color_hex};"
    else:
        st.warning(f"Background image not found at: {image_path}. Using fallback color.")
        bg_style = f"background-color: {default_color_hex};"


    st.markdown(f"""
        <style>
        /* Overall App Background */
        [data-testid="stAppViewContainer"] {{
            {bg_style}
        }}
        /* Remove default Streamlit header and toolbar background */
        [data-testid="stHeader"], [data-testid="stToolbar"] {{
            background: rgba(0, 0, 0, 0);
        }}

        /* Main Content Wrapper */
        .main .block-container {{
            background-color: rgba(0, 0, 0, 0.7); /* Semi-transparent black for readability */
            color: white;
            padding: 0px 40px 40px 40px;
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            margin-top: 50px;
            margin-bottom: 50px;
            max-width: 95vw;
        }}

        /* Add back padding to the content within the main block, specifically targeting the columns block */
        [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] {{
            padding-top: 40px;
        }}


        /* Dark-themed plot containers */
        .plot-container {{
            background-color: #1a1a1a;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}

        /* Green Header Bar for Dashboard Title and Logo/Team Name */
        .dashboard-header {{
            background-color: #000000;
            color: white;
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: left;
            font-size: 2.5em;
            font-weight: bold;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            position: relative;
            overflow: hidden;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* Adjust Streamlit specific elements for dark background */
        label, .st-b3, .st-ag, .st-be, .st-emotion-cache-nahz7x, .st-emotion-cache-1jmveob, .st-ce, .st-bi {{
            color: white !important;
        }}
        .st-emotion-cache-1r6dm1r p {{
            color: white !important;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: white !important;
        }}

        /* Table specific styling for dark theme (st.dataframe) */
        .stDataFrame {{
            background-color: black;
            color: white;
            border-radius: 10px;
            overflow: hidden;
        }}
        .stDataFrame th {{
            background-color: #333333;
            color: white;
        }}
        .stDataFrame td {{
            background-color: #1a1a1a;
            color: white;
        }}
        /* Hover effect for rows */
        .stDataFrame tbody tr:hover {{
            background-color: #2a2a2a;
        }}

        /* Ensure .stDataFrame scrollable content background is also dark */
        .stDataFrame .ag-theme-streamlit {{
            background-color: black !important;
        }}
        .stDataFrame .ag-root-wrapper, .ag-root-wrapper-body, .ag-row {{
            background-color: black !important;
        }}
        .stDataFrame .ag-cell-wrapper, .ag-row-even, .ag-row-odd {{
            background-color: #1a1a1a !important;
            color: white !important;
        }}
        .stDataFrame .ag-header-cell {{
            background-color: #333333 !important;
            color: white !important;
        }}

        /* --- Selectbox Dark Theme Styling --- */
        /* The main selectbox container (the visible bar) */
        .stSelectbox > div[data-baseweb="select"] > div:first-child {{
            background-color: #333333 !important;
            color: white !important;
            border: 1px solid #555555 !important;
            border-radius: 5px;
        }}

        /* Text inside the selectbox bar */
        .stSelectbox > div[data-baseweb="select"] > div:first-child span {{
            color: white !important;
        }}

        /* The dropdown list when opened */
        .stSelectbox > div[data-baseweb="select"] div[role="listbox"] {{
            background-color: #1a1a1a !important;
            color: white !important;
            border: 1px solid #555555 !important;
            border-radius: 5px;
        }}

        /* Individual options in the dropdown */
        .stSelectbox > div[data-baseweb="select"] div[role="option"] {{
            background-color: #1a1a1a !important;
            color: white !important;
        }}

        /* Hover effect for dropdown options */
        .stSelectbox > div[data-baseweb="select"] div[role="option"]:hover {{
            background-color: #4a4a4a !important;
            color: white !important;
        }}

        /* Currently selected option in the dropdown list */
        .stSelectbox > div[data-baseweb="select"] div[aria-selected="true"] {{
            background-color: #5a5a5a !important;
            color: white !important;
        }}

        /* Arrow icon in the selectbox */
        .stSelectbox div[data-baseweb="select"] svg {{
            fill: white !important;
        }}

        /* Tabular column headers (for st.dataframe) */
        .ag-theme-streamlit .ag-header-cell-text,
        .ag-theme-streamlit .ag-header-group-text {{
            color: white !important;
            font-weight: bold;
        }}
        .ag-theme-streamlit .ag-header-cell,
        .ag-theme-streamlit .ag-header-group-cell {{
            background-color: #333333 !important;
            border-bottom: 1px solid #555555 !important;
        }}

        /* Score Tiers & Benchmark - ONE LINE DISPLAY */
        .score-tiers-container {{
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
            flex-wrap: nowrap;
        }}
        .score-tiers-container > div {{
            display: flex;
            align-items: center;
            gap: 3px;
            font-size: 0.75em;
            white-space: nowrap;
        }}
        /* Refinement: Ensure text inside score tiers containers is white */
        .score-tiers-container div div {{ /* Targets the inner divs containing text like "Sub Par (<= 3.0)" */
            color: white !important;
        }}


        /* Styles for the insight containers */
        .insight-section-container {{
            background-color: #1a1a1a; /* Darker background for individual insight boxes */
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px; /* Add margin to separate from content above */
            margin-bottom: 15px; /* Add margin to separate from content below */
            min-height: 180px; /* Adjusted for under 100 words, still spacious */
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            border: 1px solid #333333; /* Subtle border for definition */
        }}
        .insight-section-container h3 {{
            color: white !important; /* Make headings white here, as they're inside a dark box */
            border-bottom: none; /* Remove inner border */
            padding-bottom: 5px;
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        .insight-section-container p {{
            font-size: 0.9em;
            line-height: 1.4;
            color: white !important; /* Ensure paragraph text is white */
            text-align: justify; /* Justify text for better appearance */
        }}
        /* Existing icon styles remain relevant */
        .strength-icon {{ color: #2ca02c; }}
        .focus-icon {{ color: #ff7f0e; }}
        </style>
    """, unsafe_allow_html=True)

def display_header_with_logo_and_text(title, logo_path, org_name):
    """Displays a custom header with a title, logo, and organization name."""
    encoded_logo = encode_image(logo_path)
    logo_html = f'<img src="data:image/png;base64,{encoded_logo}" style="width: 50px; height: auto;">' if encoded_logo else ''
    org_display_html = f"<div>{org_name if org_name else 'Organization'}</div>" if org_name else ""

    st.markdown(f"""
        <div class="dashboard-header">
            <h1>{title}</h1>
            <div class="header-logo-text-container">
                {logo_html}
                {org_display_html}
            </div>
        </div>
    """, unsafe_allow_html=True)

# -------------------- Data Access --------------------
def get_db_connection():
    """Establishes and returns a MySQL database connection using Streamlit Secrets."""
    try:
        conn = mysql.connector.connect(
            host=st.secrets.database.DB_HOST,
            database=st.secrets.database.DB_DATABASE,
            user=st.secrets.database.DB_USER,
            password=st.secrets.database.DB_PASSWORD
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"❌ Database connection error: {err}")
        st.error("Please ensure your database credentials in .streamlit/secrets.toml are correct.")
        return None

@st.cache_data(ttl=600)
def fetch_organization_data(_user_email):
    """
    Fetches the latest survey data for a given organization based on the user's email.
    Returns aggregated scores and organization details.
    """
    conn = get_db_connection()
    if not conn: return None, None, None

    cursor = None
    org_data = {}
    org_name = None
    admin_email_for_org = None

    try:
        cursor = conn.cursor(dictionary=True)
        # Get organization name from user's email
        cursor.execute("SELECT organisation_name FROM user_registration WHERE Email_Id = %s", (_user_email,))
        user_org_info = cursor.fetchone()

        if not user_org_info or not user_org_info.get('organisation_name'):
            st.warning(f"User '{_user_email}' not found or organization name not specified.")
            return None, None, None
        org_name = user_org_info['organisation_name']
        org_data['Organization_Name'] = org_name

        # Attempt to find an admin email for the organization
        try:
            cursor.execute("SELECT DISTINCT admin_email FROM admin_team_members WHERE organisation_name = %s LIMIT 1", (org_name,))
            admin_info = cursor.fetchone()
            if admin_info and admin_info.get('admin_email'):
                admin_email_for_org = admin_info['admin_email']
        except mysql.connector.Error as admin_err:
            print(f"DEBUG: Could not fetch admin email for {org_name}: {admin_err}")

        # Get all user emails for the organization
        cursor.execute("SELECT Email_Id FROM user_registration WHERE organisation_name = %s", (org_name,))
        org_emails_rows = cursor.fetchall()
        org_emails = [row['Email_Id'] for row in org_emails_rows if row.get('Email_Id')]

        if not org_emails:
            st.warning(f"No users found for organization '{org_name}'.")
            return org_data, org_name, admin_email_for_org

        # Define tables and their relevant columns
        tables_and_db_cols = {
            "Leadership": ["Leadership_avg", "Leadership_StrategicPlanning", "Leadership_ExternalEnvironment", "Leadership_Resources", "Leadership_Governance"],
            "Empower": ["Empower_avg", "Empower_Feedback", "Empower_ManagingRisk", "Empower_DecisionMaking", "Empower_RecoverySystems"],
            "Sustainability": ["Sustainability_avg", "Sustainability_LongTermPlanning", "Sustainability_ResourceManagement", "Sustainability_EnvironmentalImpact", "Sustainability_StakeholderEngagement"],
            "CulturePulse": ["CulturePulse_avg", "CulturePulse_Values", "CulturePulse_Respect", "CulturePulse_Communication", "CulturePulse_Diversity"],
            "Bonding": ["Bonding_avg", "Bonding_PersonalGrowth", "Bonding_Negotiation", "Bonding_GroupCohesion", "Bonding_Support"],
            "Influencers": ["Influencers_avg", "Influencers_Funders", "Influencers_Sponsors", "Influencers_PeerGroups", "Influencers_ExternalAlliances"]
        }
        all_latest_user_data = []

        # Fetch the latest survey data for each user from each relevant table
        for table, cols_to_select in tables_and_db_cols.items():
            inner_select_cols_list = [f"`{col}`" for col in cols_to_select]
            inner_select_cols_str = ", ".join(inner_select_cols_list + ["`Email_Id`", "`submission_id`"])
            outer_select_cols_str = ", ".join(inner_select_cols_list)

            placeholders = ','.join(['%s'] * len(org_emails))
            query = f"""
            SELECT {outer_select_cols_str}
            FROM (
                SELECT {inner_select_cols_str},
                        ROW_NUMBER() OVER(PARTITION BY `Email_Id` ORDER BY `submission_id` DESC) as rn
                FROM `{table}`
                WHERE `Email_Id` IN ({placeholders})
            ) ranked_data
            WHERE rn = 1;
            """
            try:
                cursor.execute(query, tuple(org_emails))
                latest_entries_for_table = cursor.fetchall()
                all_latest_user_data.extend(latest_entries_for_table)
            except mysql.connector.Error as table_err:
                st.warning(f"Could not fetch data from table '{table}': {table_err}.")

        if not all_latest_user_data:
            st.warning(f"No survey data found for any user in organization '{org_name}'.")
            return org_data, org_name, admin_email_for_org

        df_combined = pd.DataFrame(all_latest_user_data)
        if df_combined.empty:
            st.warning(f"Survey data for organization '{org_name}' is empty.")
            return org_data, org_name, admin_email_for_org

        # Filter for only the score columns that actually exist in the fetched data
        score_cols_defined = [col for sublist in tables_and_db_cols.values() for col in sublist]
        score_cols_to_process = [col for col in score_cols_defined if col in df_combined.columns]

        if not score_cols_to_process:
            st.warning(f"No relevant score columns found for '{org_name}'.")
            return org_data, org_name, admin_email_for_org

        # Convert scores to numeric and calculate averages
        df_scores = df_combined[score_cols_to_process].copy()
        for col in df_scores.columns:
            df_scores[col] = pd.to_numeric(df_scores[col], errors='coerce')

        org_averages = df_scores.mean().round(2).to_dict()
        org_data.update(org_averages)
        return org_data, org_name, admin_email_for_org

    except Exception as e:
        st.error(f"❌ An unexpected error occurred during data fetching: {e}")
        return None, None, None
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# -------------------- Plot Functions (for main categories and donuts) --------------------
def plot_category_scores(scores_data, sub_variables_map, benchmark=5.5):
    """Generates a bar chart for overall category scores against a benchmark."""
    scores = {cat_name.replace(" ", ""): float(scores_data.get(f"{cat_name.replace(' ', '')}_avg", 0.0)) for cat_name in sub_variables_map.keys()}

    filtered_scores = {k: v for k, v in scores.items() if v > 0}  # Only plot categories with data

    if not any(s > 0 for s in scores.values()):
        fig = go.Figure()
        fig.update_layout(title_text="No overall category data available for plotting.",
                          title_font_color='white',
                          xaxis={'visible': False}, yaxis={'visible': False},
                          paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)')
        return fig

    plot_categories = list(filtered_scores.keys())
    plot_values = list(filtered_scores.values())

    # Assign colors based on performance tiers
    colors = []
    for v in plot_values:
        if v <= 3.0:
            colors.append('#d62728') # Sub Par (Red)
        elif v <= 5.0:
            colors.append('#ff7f0e') # Decent (Orange)
        else:
            colors.append('#2ca02c') # Top Tier (Green)

    fig = go.Figure(go.Bar(x=plot_categories, y=plot_values, marker_color=colors, text=[f'{v:.2f}' for v in plot_values], textposition='outside'))

    # Add benchmark line if there are categories to plot
    if plot_categories:
        fig.add_shape(type="line", x0=-0.5, y0=benchmark, x1=len(plot_categories)-0.5, y1=benchmark, line=dict(color="white", dash="dash", width=2))

    fig.update_layout(
        title_text="Overall Performance Across Elements",
        title_font_color='white',
        yaxis=dict(range=[0, 7.5], title='Average Scores (1-7 Scale)', title_font_color='white', tickfont_color='white'),
        xaxis=dict(title='Elements', title_font_color='white', tickfont_color='white'),
        paper_bgcolor='rgba(0,0,0,0)', # Transparent paper background
        plot_bgcolor='#1a1a1a'  # Dark plot background
    )
    # Refinement: Set font color of scores on the bars to white
    fig.update_traces(textfont_color='white')
    return fig

def plot_sub_variable_donut_charts(scores_data, category_display_name, sub_vars_conceptual, max_score=7.0):
    """Generates donut charts for individual sub-variables within a selected category."""
    db_key_prefix = category_display_name.replace(" ", "")

    sub_scores_to_plot = []
    for sub_conceptual in sub_vars_conceptual:
        score_key = f"{db_key_prefix}_{sub_conceptual}"
        score = float(scores_data.get(score_key, 0.0))
        if score > 0: # Only plot if score exists and is valid
            sub_scores_to_plot.append({"name": sub_conceptual, "score": score})

    if not sub_scores_to_plot:
        st.info(f"No sub-variable data available for {category_display_name} to plot donut charts.")
        return

    num_sub_vars = len(sub_scores_to_plot)
    MAX_CHARTS_PER_ROW = 4

    def format_title_for_donut(name):
        """Formats sub-variable names for donut chart titles."""
        res = ""
        for char_index, char in enumerate(name):
            if char_index > 0 and char.isupper(): # Add line break before uppercase letters (e.g., "StrategicPlanning" -> "Strategic<br>Planning")
                res += "<br>"
            res += char
        return res

    # Arrange donut charts in rows
    for i in range(0, num_sub_vars, MAX_CHARTS_PER_ROW):
        charts_in_this_row_data = sub_scores_to_plot[i:i + MAX_CHARTS_PER_ROW]
        num_charts_in_row = len(charts_in_this_row_data)

        # Create columns to center charts if fewer than MAX_CHARTS_PER_ROW
        spacer_width = (MAX_CHARTS_PER_ROW - num_charts_in_row) / 2.0

        col_spec = []
        if spacer_width > 0:
            col_spec.append(spacer_width)

        col_spec.extend([1] * num_charts_in_row) # Equal width for charts

        if spacer_width > 0:
            col_spec.append(spacer_width)

        row_cols = st.columns(col_spec)
        chart_col_start_index = 1 if spacer_width > 0 else 0

        for j, sub_data in enumerate(charts_in_this_row_data):
            col_to_plot_in = row_cols[chart_col_start_index + j]
            with col_to_plot_in:
                sub_var_name = sub_data["name"]
                score = sub_data["score"]
                formatted_title = format_title_for_donut(sub_var_name)
                remaining = max_score - score
                labels = ['Achieved Score', 'Remaining']
                values = [score, remaining]

                # Determine color based on score tier (for the segment color)
                if score <= 3.0:
                    score_color_segment = '#d62728'
                elif score <= 5.0:
                    score_color_segment = '#ff7f0e'
                else:
                    score_color_segment = '#2ca02c'

                fig = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=.7, # Makes it a donut chart
                    marker_colors=[score_color_segment, '#e0e0e0'], # Color for score, light gray for remaining
                    direction='clockwise',
                    sort=False,
                    hoverinfo='label+percent',
                    textinfo='none' # Hide labels/percentages directly on chart, show score in center
                )])

                fig.update_layout(
                    title_text=formatted_title,
                    title_font_size=16,
                    title_font_color='white',
                    annotations=[dict(text=f'{score:.2f}', x=0.5, y=0.5, font_size=20, showarrow=False,
                                        font_color='white')], # Changed to 'white'
                    showlegend=False,
                    height=250,
                    width=250,
                    margin=dict(l=20, r=20, t=60, b=20),
                    paper_bgcolor='rgba(0,0,0,0)', # Transparent paper background
                    plot_bgcolor='#1a1a1a' # Dark plot background
                )

                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def display_sub_category_performance_table(org_data, sub_variables_conceptual, performance_type="Best", num_categories=5):
    """
    Generates a DataFrame for either best or worst performing sub-categories with color styling.
    """
    all_sub_category_scores = []
    for main_cat, sub_vars in sub_variables_conceptual.items():
        db_key_prefix = main_cat.replace(" ", "")
        for sub_name in sub_vars:
            score_key = f"{db_key_prefix}_{sub_name}"
            score = org_data.get(score_key, 0.0)
            if score > 0: # Only include sub-categories with actual data
                # Use a more readable display name for the table
                display_name = f"{main_cat} - {sub_name}"
                all_sub_category_scores.append({"Sub-Category": display_name, "Score": float(score)})

    if not all_sub_category_scores:
        # Return empty DataFrames if no sub-category data is available
        return pd.DataFrame(), pd.DataFrame()

    df_all_scores = pd.DataFrame(all_sub_category_scores)

    if performance_type == "Best":
        df_display = df_all_scores.sort_values(by="Score", ascending=False).head(num_categories).copy()
    elif performance_type == "Worst":
        df_display = df_all_scores.sort_values(by="Score", ascending=True).head(num_categories).copy()
    else:
        st.error("Invalid performance type. Please select 'Best' or 'Worst'.")
        return pd.DataFrame(), pd.DataFrame()

    # Apply styling function
    def color_score(val):
        """
        Colors the score based on the performance tier.
        """
        try:
            val = float(val)
            if val <= 3.0:
                return 'background-color: #d62728; color: white;' # Sub Par (Red)
            elif val <= 5.0:
                return 'background-color: #ff7f0e; color: white;' # Decent (Orange)
            else:
                return 'background-color: #2ca02c; color: white;' # Top Tier (Green)
        except ValueError:
            return '' # No styling for non-numeric values

    # Apply styling to the 'Score' column
    styled_df = df_display.style.applymap(color_score, subset=['Score'])

    return styled_df, df_display # Return both the styled DataFrame and the raw DataFrame for insights

def generate_dynamic_insight_text(df_best_performing, df_worst_performing, benchmark_value):
    """
    Generates dynamic strength and area for focus text based on performance data.
    Ensures text is concise (under 100 words per section).
    """
    strengths_text = "No specific strengths identified based on current organizational performance data."
    areas_for_focus_text = "No specific areas for focus identified based on current organizational performance data."

    # --- Strengths ---
    if not df_best_performing.empty:
        # Limit to top 2-3 items for conciseness
        top_items = df_best_performing.head(2) # Limiting to 2 for tighter word count
        strength_phrases = [f"{row['Sub-Category']} (Score {row['Score']:.1f})" for index, row in top_items.iterrows()]

        if strength_phrases:
            strength_list_str = ", ".join(strength_phrases)
            strengths_template = (
                f"Our organization demonstrates significant strengths, particularly in {strength_list_str}. "
                f"These high scores, consistently above the benchmark of {benchmark_value}, reflect strong strategic alignment and effective resource utilization. "
                "This indicates a robust foundation for sustained success and an empowered workforce. Continuous leveraging of these areas is key."
            )
            # Basic word count management
            if len(strengths_template.split()) > 95:
                strengths_text = " ".join(strengths_template.split()[:95]) + "..."
            else:
                strengths_text = strengths_template
        else:
            strengths_text = "Key strengths were not clearly defined in the current performance data."


    # --- Areas for Focus ---
    if not df_worst_performing.empty:
        # Limit to bottom 2-3 items for conciseness
        bottom_items = df_worst_performing.head(2) # Limiting to 2 for tighter word count
        focus_phrases = [f"{row['Sub-Category']} (Score {row['Score']:.1f})" for index, row in bottom_items.iterrows()]

        if focus_phrases:
            focus_list_str = ", ".join(focus_phrases)
            focus_template = (
                f"Areas for immediate attention include {focus_list_str}. "
                f"Scores in these segments, below the benchmark of {benchmark_value}, suggest opportunities to enhance communication clarity and refine decision-making processes. "
                "Targeted efforts here can significantly boost overall organizational performance and resilience."
            )
            # Basic word count management
            if len(focus_template.split()) > 95:
                areas_for_focus_text = " ".join(focus_template.split()[:95]) + "..."
            else:
                areas_for_focus_text = focus_template
        else:
            areas_for_focus_text = "Areas for improvement were not clearly defined in the current performance data."

    return strengths_text, areas_for_focus_text


# -------------------- Email Functions --------------------
def send_email_with_attachment(recipient_email, subject, body_text, pdf_bytes=None, filename="dashboard.pdf"):
    """Sends an email with plain text body and an optional PDF attachment using Streamlit Secrets."""
    try:
        sender_email = st.secrets.email.SENDER_EMAIL
        sender_password = st.secrets.email.SENDER_APP_PASSWORD
        smtp_server = st.secrets.email.SMTP_SERVER
        smtp_port = st.secrets.email.SMTP_PORT
    except (AttributeError, KeyError):
        st.error("Email configuration is missing from Streamlit secrets. Please check your .streamlit/secrets.toml file.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain'))

    if pdf_bytes:
        part = MIMEApplication(pdf_bytes, Name=filename)
        part['Content-Disposition'] = f'attachment; filename="{filename}"'
        msg.attach(part)

    server = None
    try:
        if smtp_port == 465: # Use SSL for port 465
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else: # Use STARTTLS for other ports (e.g., 587)
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        
    except smtplib.SMTPAuthenticationError:
        st.error("Email sending failed: Authentication error. Check your sender email and app password in Streamlit secrets.")
        return False
    except smtplib.SMTPConnectError as e:
        st.error(f"Email sending failed: Could not connect to SMTP server at {smtp_server}:{smtp_port}. Error: {e}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred while sending email: {e}")
        return False
    finally:
        if server:
            server.quit()
    return True

def format_results_for_email(org_data_full, sub_variables_conceptual, benchmark_value):
    """Formats the organizational performance data into a readable text string for email."""
    org_name = org_data_full.get('Organization_Name', "N/A")
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = f"Organizational Performance Report\nOrganization: {org_name}\nReport Date: {report_date}\n\n"
    body += f"Organizational Benchmark: {benchmark_value}\n\nScore Tiers (based on 1-7 scale):\n- Sub Par (<= 3.0)\n- Decent (3.1 - 5.0)\n- Top Tier (> 5.0)\n\n"
    body += "--- Overall Performance (Average Scores) ---\n"
    for cat_name in sub_variables_conceptual.keys():
        avg_key = f"{cat_name.replace(' ', '')}_avg"
        score = org_data_full.get(avg_key, "N/A")
        body += f"- {cat_name}: {score}\n"
    body += "\n--- Detailed Sub-Element Analysis (Average Scores) ---\n"
    for main_cat, sub_vars in sub_variables_conceptual.items():
        body += f"\n>> Element: {main_cat}\n"
        for sub_name in sub_vars:
            score_key = f"{main_cat.replace(' ', '')}_{sub_name}"
            score = org_data_full.get(score_key, "N/A")
            body += f"    - {sub_name}: {score}\n"
    body += "\n\nThis is an automated report."
    return body

# -------------------- Main Dashboard ------------------
def dashboard(navigate_to, user_email):
    """Renders the main dashboard page."""

    set_background(BG_IMAGE_PATH) # Set background image

    # Fetch organization data, or retrieve from session state
    org_data_key = f"org_data_{user_email}"
    if org_data_key not in st.session_state:
        with st.spinner("Fetching organization data..."):
            st.session_state[org_data_key] = fetch_organization_data(user_email)

    fetched_data_tuple = st.session_state.get(org_data_key)
    if not fetched_data_tuple or fetched_data_tuple[0] is None:
        st.warning("Organization data could not be loaded. Please check user email or database connection.")
        if st.button("Retry Data Load"):
            if org_data_key in st.session_state: del st.session_state[org_data_key]
            st.rerun()
        return

    org_data, org_name_from_fetch, admin_email = fetched_data_tuple
    current_org_name = org_name_from_fetch or (org_data.get('Organization_Name') if org_data else "Organization")

    display_header_with_logo_and_text("Organisational Performance Dashboard", LOGO_PATH, current_org_name)

    if not org_data:
        st.warning("Essential organization data is missing. Dashboard cannot be displayed.")
        return

    # Define the conceptual mapping of main categories to their sub-variables
    sub_variables_conceptual = {
        "Leadership": ["StrategicPlanning", "ExternalEnvironment", "Resources", "Governance"],
        "Empower": ["Feedback", "ManagingRisk", "DecisionMaking", "RecoverySystems"],
        "Sustainability": ["LongTermPlanning", "ResourceManagement", "EnvironmentalImpact", "StakeholderEngagement"],
        "CulturePulse": ["Values", "Respect", "Communication", "Diversity"],
        "Bonding": ["PersonalGrowth", "Negotiation", "GroupCohesion", "Support"],
        "Influencers": ["Funders", "Sponsors", "PeerGroups", "ExternalAlliances"]
    }
    benchmark_value = 5.5 # Example benchmark score
    data_for_plotting = {k: v for k, v in org_data.items() if k != 'Organization_Name'} # Exclude org name for score plotting

    col1, col2 = st.columns([2, 1.2]) # Layout with two columns

    # === LEFT COLUMN: CHARTS & STRENGTHS ===
    with col1:
        # Overall Scores Plot (Bar Chart)
        if not data_for_plotting:
            st.warning("No performance data available for plotting the overall scores.")
        else:
            fig_overall_scores = plot_category_scores(data_for_plotting, sub_variables_conceptual, benchmark=benchmark_value)
            st.plotly_chart(fig_overall_scores, use_container_width=True)

        # Detailed Sub-Element Analysis (Donut Charts)
        st.subheader(f"Detailed Sub-Element Analysis:")
        category_for_detail = st.selectbox(
            "Select an Element for Detailed Analysis",
            list(sub_variables_conceptual.keys()),
            key="category_selection",
            index=0,
            label_visibility="collapsed"
        )

        plot_sub_variable_donut_charts(data_for_plotting, category_for_detail, sub_variables_conceptual[category_for_detail])

        # Get data for insights tables
        # Use a dummy df if data_for_plotting is empty to prevent errors in generate_dynamic_insight_text
        if not data_for_plotting:
            df_best_performing_for_insights = pd.DataFrame(columns=["Sub-Category", "Score"])
            df_worst_performing_for_insights = pd.DataFrame(columns=["Sub-Category", "Score"])
        else:
            # We call display_sub_category_performance_table just to get the raw dataframe for insights
            # The styled dataframe is not used directly here, but the function returns both.
            _, df_best_performing_for_insights = display_sub_category_performance_table(
                data_for_plotting,
                sub_variables_conceptual,
                "Best",
                num_categories=3 # Only need a few for insight generation
            )
            _, df_worst_performing_for_insights = display_sub_category_performance_table(
                data_for_plotting,
                sub_variables_conceptual,
                "Worst",
                num_categories=3 # Only need a few for insight generation
            )

        # Generate dynamic insight texts
        strengths_content, areas_for_focus_content = generate_dynamic_insight_text(
            df_best_performing_for_insights,
            df_worst_performing_for_insights,
            benchmark_value
        )

        # STRENGTHS section moved here
        st.markdown(f"<div class='insight-section-container'><h3><span class='strength-icon'>✅</span> Strengths:</h3><p>{strengths_content}</p></div>", unsafe_allow_html=True)


    # === RIGHT COLUMN: CONTROLS, TABLES & ACTIONS & AREAS FOR IMPROVEMENT ===
    with col2:
        # Score Tiers & Benchmark container for easy reference
        with st.container():
            st.subheader("Score Tiers & Benchmark")
            st.markdown(f"**Organizational Benchmark** = `{benchmark_value}`") # This text is handled by general CSS
            score_tiers_html = """
            <div class="score-tiers-container">
                <div><div style="width: 20px; height: 20px; background-color: #d62728; border-radius: 3px;"></div><div><b>Sub Par</b> (&le; 3.0)</div></div>
                <div><div style="width: 20px; height: 20px; background-color: #ff7f0e; border-radius: 3px;"></div><div><b>Decent</b> (3.1 - 5.0)</div></div>
                <div><div style="width: 20px; height: 20px; background-color: #2ca02c; border-radius: 3px;"></div><div><b>Top Tier</b> (&gt; 5.0)</div></div>
            </div>
            """
            st.markdown(score_tiers_html, unsafe_allow_html=True)

        # Sub-Category Performance Highlights - TABULAR
        with st.container():
            st.subheader("Sub-Category Performance Highlights")

            performance_selection = st.selectbox(
                "Select Performance Type",
                ("Best", "Worst"),
                key="performance_type_selection_table",
            )

            if not data_for_plotting:
                st.info(f"No sub-category data available for the {performance_selection.lower()} performing sub-categories to display.")
            else:
                styled_df_display, _ = display_sub_category_performance_table(
                    data_for_plotting,
                    sub_variables_conceptual,
                    performance_selection,
                    num_categories=5
                )
                st.dataframe(styled_df_display, use_container_width=True, hide_index=True)


        # Actions Container - Send email with results
        st.subheader("Actions")
        if admin_email:
            if st.button(f"📄 Email Full Text Results to Admin", key="email_text_results", use_container_width=True):
                with st.spinner(f"Preparing and sending results to {admin_email}..."):
                    email_subject = f"{current_org_name} - Full Performance Results - {datetime.now().strftime('%Y-%m-%d')}"
                    email_body = format_results_for_email(org_data, sub_variables_conceptual, benchmark_value)
                    if send_email_with_attachment(admin_email, email_subject, email_body):
                        st.success(f"Results successfully emailed to {admin_email}!")
                    else:
                        st.error("Failed to send email. Please check logs and your secret credentials for details.")
        else:
            st.info("Admin email not found for this organization. Emailing results is unavailable.")

        # Navigation for other VClarifi agents
        st.subheader("Explore VClarifi Agents")
        nav_cols_inner = st.columns(2)
        with nav_cols_inner[0]:
            if st.button("➡ Recommendations", key="to_reco", use_container_width=True):
                navigate_to("Recommendations")
            if st.button("➡ DocBot", key="to_docbot", use_container_width=True):
                navigate_to("docbot")
        with nav_cols_inner[1]:
            if st.button("➡ VClarifi Agent", key="to_agent", use_container_width=True):
                navigate_to("VClarifi_Agent")
            if st.button("➡ Text-to-Video", key="to_t2v", use_container_width=True):
                navigate_to("text_2_video_agent")

        # AREAS FOR IMPROVEMENT section moved here
        st.markdown(f"<div class='insight-section-container' style='margin-top: 30px;'><h3><span class='focus-icon'>🎯</span> Areas for Focus:</h3><p>{areas_for_focus_content}</p></div>", unsafe_allow_html=True)


def placeholder_page(title, navigate_to):
    """A generic placeholder page for features not yet implemented."""

    set_background(BG_IMAGE_PATH) # Use background image for placeholder pages too

    current_org_name = st.session_state.get('org_name_for_header', "Organization")
    display_header_with_logo_and_text(title, LOGO_PATH, current_org_name)

    st.info(f"'{title.replace('💡 ', '').replace('🤖 ', '').replace('📄 ', '').replace('🎥 ', '')}' feature is not yet implemented. Stay tuned!")
    st.markdown("---")
    if st.button("⬅ Back to Dashboard", key=f"back_dash_{title.replace(' ', '_')}"):
        navigate_to("Dashboard")

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="VClarifi Dashboard")

    # Initialize session state variables if they don't exist
    if 'user_email' not in st.session_state:
        st.session_state['user_email'] = 'admin_alpha@example.com'
    if 'page' not in st.session_state:
        st.session_state['page'] = 'Dashboard'
    if 'org_name_for_header' not in st.session_state:
        st.session_state['org_name_for_header'] = 'Loading...'

    # Function to change page in Streamlit
    def nav_to(page_name):
        st.session_state['page'] = page_name
        st.rerun()

    # Ensures the organization name is fetched and set for headers on non-dashboard pages
    def ensure_org_name_for_header_on_demand():
        if st.session_state.get('org_name_for_header') == 'Loading...' or not st.session_state.get('org_name_for_header'):
            _, org_name, _ = fetch_organization_data(st.session_state['user_email'])
            st.session_state.org_name_for_header = org_name or "Organization"

    # Map pages to their respective functions
    page_map = {
        "Dashboard": lambda: dashboard(nav_to, st.session_state.user_email),
        "Recommendations": lambda: placeholder_page("💡 Recommendations", nav_to),
        "VClarifi_Agent": lambda: placeholder_page("🤖 VClarifi Agent", nav_to),
        "docbot": lambda: placeholder_page("📄 DocBot", nav_to),
        "text_2_video_agent": lambda: placeholder_page("🎥 Text-to-Video Agent", nav_to),
    }

    # Render the current page
    current_page_func = page_map.get(st.session_state.page)
    if current_page_func:
        if st.session_state.page != "Dashboard":
            ensure_org_name_for_header_on_demand()
        current_page_func()
    else:
        st.error("Page not found.")