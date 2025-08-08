import base64
import os
import streamlit as st
from PyPDF2 import PdfReader
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

# --- Constants ---
BG_IMAGE_PATH = "C:/Users/DELL/Desktop/background.jpg"
LOGO_IMAGE_PATH = "C:/Users/DELL/Desktop/VTARA.png"
AVATAR_USER_PATH = "images/avatar_user.png"
AVATAR_BOT_PATH = "images/avatar_chatbot.png"

# --- REFINED: API Key Configuration ---
# The code now exclusively reads the API key from your Streamlit secrets file.
# Please ensure your .streamlit/secrets.toml file contains:
#
# groq_apiReadKey = "gsk_..."

try:
    # Access the key directly from secrets.
    groq_api_key_to_use = st.secrets.groq_apiReadKey
except (AttributeError, KeyError):
    # Set to None if not found; the app will display a clear error message below.
    groq_api_key_to_use = None

# --- Helper functions ---
def encode_image_to_base64(image_path):
    try:
        if not os.path.isabs(image_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            image_path = os.path.join(script_dir, image_path)

        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.warning(f"Image file not found: {image_path}.")
        return None
    except Exception as e:
        st.warning(f"Error encoding image {image_path}: {e}")
        return None

def set_docbot_background_style(image_path):
    encoded_bg = encode_image_to_base64(image_path)
    if encoded_bg:
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("data:image/jpeg;base64,{encoded_bg}");
                background-size: cover; background-position: center; background-repeat: no-repeat;
                color: white;
            }}
            [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{ background: none; }}
            [data-testid="stHeader"] {{ background: rgba(0, 0, 0, 0); }}
            [data-testid="stSidebar"] > div:first-child {{
                background-color: rgba(0, 0, 0, 0.4); border-radius: 10px; padding: 20px;
            }}
            .block-container {{ padding-top: 3vh; max-width: 95vw; }}
            h1, h2, h3, h4, h5, h6, p, div, span, label, li {{ color: white !important; }}
            .stTextInput > div > div > input, .stTextArea > div > div > textarea {{
                color: #333 !important; background-color: rgba(255, 255, 255, 0.95) !important;
                border-radius: 5px;
            }}
            div.stButton > button {{
                background-color: #008CBA;
                color: white;
                border: 2px solid #008CBA;
                border-radius: 8px;
                padding: 10px 24px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 4px 2px;
                transition-duration: 0.4s;
                cursor: pointer;
                width: 100%;
            }}
            div.stButton > button:hover {{
                background-color: white;
                color: black;
                border: 2px solid #008CBA;
            }}
            div[data-testid^="stChatMessage"] div[data-testid^="stMarkdownContainer"] p {{
                color: white !important;
            }}
            div[data-testid^="stChatMessage"] > div {{
                border-radius: 18px; padding: 12px 18px;
                box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3); margin-bottom: 12px;
            }}
            .sidebar-status-ok {{ color: #90EE90 !important; font-weight: bold;}}
            .sidebar-status-warn {{ color: #FFD700 !important; font-weight: bold;}}
            .sidebar-status-error {{ color: #FF6347 !important; font-weight: bold;}}
            .sidebar-status-info {{ color: #ADD8E6 !important; }}
            </style>
        """, unsafe_allow_html=True)

def display_docbot_logo_and_title(logo_path):
    encoded_logo = encode_image_to_base64(logo_path)
    if encoded_logo:
        st.markdown(f"""
            <style>
                .vclarifi-header {{
                    position: absolute; top: 15px; right: 25px; display: flex;
                    align-items: center; gap: 12px; z-index: 1000;
                }}
                .vclarifi-header img {{ width: 65px; max-width: 15vw; height: auto; }}
                .vclarifi-header div {{
                    font-family: 'Arial Black', Gadget, sans-serif;
                    font-size: clamp(1.8vw, 2vw, 2.5vw); font-weight: bold;
                    color: white; text-shadow: 2px 2px 4px rgba(0,0,0,0.6);
                }}
            </style>
            <div class="vclarifi-header">
                <img src="data:image/png;base64,{encoded_logo}" alt="VCLARIFI Logo">
                <div>VCLARIFI</div>
            </div>
        """, unsafe_allow_html=True)

def load_pdfs_and_extract_text(uploaded_files):
    docs, extracted_texts_info = [], []
    for pdf_file in uploaded_files:
        try:
            pdf_reader = PdfReader(pdf_file)
            text_content = ""
            for page in pdf_reader.pages:
                extracted_page_text = page.extract_text()
                if extracted_page_text:
                    text_content += extracted_page_text + '\n\n'
            if text_content.strip():
                docs.append(Document(page_content=text_content, metadata={"source": pdf_file.name}))
                extracted_texts_info.append(f"✅ Successfully extracted text from '{pdf_file.name}'.")
            else:
                extracted_texts_info.append(f"⚠️ No text could be extracted from '{pdf_file.name}'.")
        except Exception as e:
            extracted_texts_info.append(f"❌ Error reading '{pdf_file.name}': {str(e)[:100]}...")
            st.error(f"Failed to process {pdf_file.name}: {e}")
    return docs, extracted_texts_info

def create_vector_store_from_docs(docs):
    if not docs:
        st.session_state.docbot_ask_status_message = "<p class='sidebar-status-error'>No valid documents to embed. ❌</p>"
        st.session_state.docbot_vectorstore_ready = False
        return
    try:
        embedding_model = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        final_document_chunks = text_splitter.split_documents(docs)

        if not final_document_chunks:
            st.session_state.docbot_ask_status_message = "<p class='sidebar-status-error'>Documents couldn't be split. ❌</p>"
            st.session_state.docbot_vectorstore_ready = False
            return

        st.session_state.docbot_vectors = FAISS.from_documents(final_document_chunks, embedding_model)
        st.session_state.docbot_vectorstore_ready = True
        st.session_state.docbot_ask_status_message = f"<p class='sidebar-status-ok'>Docs embedded! ({len(final_document_chunks)} chunks). Ready to answer. ✅</p>"
    except Exception as e:
        st.error(f"Error during document embedding: {e}")
        st.session_state.docbot_ask_status_message = f"<p class='sidebar-status-error'>⚠️ Error embedding documents: {str(e)[:100]}...❌</p>"
        st.session_state.docbot_vectorstore_ready = False

def display_chat_message_styled(content, is_user=False):
    alignment = "flex-end" if is_user else "flex-start"
    bubble_background = "linear-gradient(135deg, #FF6B6B, #FFC371)" if is_user else "linear-gradient(135deg, #54A0FF, #8EFAFA)"
    avatar_path = AVATAR_USER_PATH if is_user else AVATAR_BOT_PATH
    avatar_base64 = encode_image_to_base64(avatar_path)
    avatar_html = f'<img src="data:image/png;base64,{avatar_base64}" style="width: 38px; height: 38px; border-radius: 50%; margin: 0 10px; align-self: flex-end;" alt="Avatar">' if avatar_base64 else ''
    processed_content = content.replace("\n", "<br>")
    message_html = f"""
    <div style="display: flex; justify-content: {alignment}; margin-bottom: 12px; align-items: flex-start;">
        {avatar_html if not is_user else ""}
        <div style="display: inline-block; padding: 12px 18px; border-radius: 18px; background: {bubble_background}; color: white; max-width: 78%; word-wrap: break-word; font-size: 0.9em; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3); line-height: 1.5;">
            {processed_content}
        </div>
        {avatar_html if is_user else ""}
    </div>
    """
    st.markdown(message_html, unsafe_allow_html=True)

# --- Main Page Function ---
def docbot(navigate_to):
    try:
        st.set_page_config(page_title="VCLARIFI DOCBOT", page_icon="🤖", layout="wide")
    except st.errors.StreamlitAPIException:
        pass # Already set

    if not groq_api_key_to_use:
        st.error("🚨 GROQ API Key not configured.")
        st.info("Please add your Groq API key to your .streamlit/secrets.toml file and restart the app.")
        st.code("Example .streamlit/secrets.toml:\n\ngroq_apiReadKey = \"gsk_...\"")
        return

    try:
        llm = ChatGroq(model_name='gemma2-9b-it', groq_api_key=groq_api_key_to_use)
    except Exception as e:
        st.error(f"🚨 Failed to initialize LLM with Groq: {e}.")
        return

    set_docbot_background_style(BG_IMAGE_PATH)
    display_docbot_logo_and_title(LOGO_IMAGE_PATH)

    default_session_state = {
        'docbot_vectorstore_ready': False,
        'docbot_ask_status_message': "<p class='sidebar-status-info'>Upload PDF documents to begin.</p>",
        'docbot_chat_history': [],
        'docbot_processing_initiated': False,
    }
    for key, value in default_session_state.items():
        st.session_state.setdefault(key, value)

    st.title("VCLARIFI DOCBOT")
    st.subheader("Your Intelligent Document Assistant - Ask anything about uploaded PDFs!")

    with st.sidebar:
        st.subheader('VCLARIFI DOCBOT 🤖')
        st.markdown("---")
        st.subheader('1. Upload PDF Files')
        uploaded_files = st.file_uploader(
            'Choose PDF files', type="pdf", accept_multiple_files=True,
            key="docbot_file_uploader_widget"
        )

        if uploaded_files:
            if not st.session_state.get('docbot_processing_initiated') or st.session_state.get('docbot_last_uploaded_files') != uploaded_files:
                st.session_state.docbot_processing_initiated = True
                st.session_state.docbot_last_uploaded_files = uploaded_files
                st.session_state.docbot_vectorstore_ready = False
                with st.spinner("Reading PDF files..."):
                    docs, extraction_infos = load_pdfs_and_extract_text(uploaded_files)
                for info in extraction_infos:
                    css_class = "sidebar-status-ok" if "✅" in info else ("sidebar-status-warn" if "⚠️" in info else "sidebar-status-error")
                    st.markdown(f"<p class='{css_class}'>{info}</p>", unsafe_allow_html=True)
                if docs:
                    st.session_state.docbot_final_document_chunks_from_load = docs
                    st.session_state.docbot_ask_status_message = "<p class='sidebar-status-info'>Click 'Embed Documents' to process.</p>"
                st.rerun()

        if st.session_state.get('docbot_final_document_chunks_from_load') and not st.session_state.get('docbot_vectorstore_ready'):
            st.markdown("---")
            st.subheader('2. Embed Documents')
            st.markdown(st.session_state.docbot_ask_status_message, unsafe_allow_html=True)
            if st.button('Embed Documents', key='docbot_embed_button_widget'):
                with st.spinner("⏳ Embedding documents... This may take a moment."):
                    create_vector_store_from_docs(st.session_state.docbot_final_document_chunks_from_load)
                st.rerun()

        if st.session_state.get('docbot_vectorstore_ready'):
            st.markdown(st.session_state.docbot_ask_status_message, unsafe_allow_html=True)

    chat_container = st.container()
    with chat_container:
        if st.session_state.docbot_chat_history:
            for message in st.session_state.docbot_chat_history:
                display_chat_message_styled(message['content'], is_user=(message['role'] == 'user'))

    user_prompt = st.chat_input(
        placeholder='Ask about your document(s)...',
        disabled=not st.session_state.docbot_vectorstore_ready,
        key='docbot_user_chat_input_widget'
    )

    if user_prompt and st.session_state.docbot_vectorstore_ready:
        st.session_state.docbot_chat_history.append({"role": "user", "content": user_prompt})
        with st.spinner("VCLARIFI DOCBOT is thinking... 🤔"):
            try:
                retriever = st.session_state.docbot_vectors.as_retriever()
                system_prompt_template = (
                    "You are VCLARIFI DOCBOT. Answer questions *only* from the provided context. "
                    "If the answer isn't in the context, state that. Do not invent information. "
                    "Context:\n<context>{context}</context>"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ('system', system_prompt_template), ('human', '{input}'),
                ])
                document_chain = create_stuff_documents_chain(llm, prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                response = retrieval_chain.invoke({'input': user_prompt})
                bot_response = response.get('answer', "Sorry, I couldn't generate a response.")
            except Exception as e:
                bot_response = f"⚠️ An error occurred: {e}"
            st.session_state.docbot_chat_history.append({"role": "assistant", "content": bot_response})
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("Back", key="docbot_go_back_widget"):
        if callable(navigate_to):
            navigate_to('Dashboard')
        else:
            st.sidebar.warning("Navigation is not available in this mode.")

if __name__ == "__main__":
    def mock_navigate_to(page_name):
        st.sidebar.success(f"Mock Navigation: Would go to '{page_name}'.")

    if not os.path.exists("images"):
        os.makedirs("images")
        st.warning("Created 'images' folder. Please add your avatar images there.")

    docbot(mock_navigate_to)