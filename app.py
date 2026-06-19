# pyrefly: ignore [missing-import]
import streamlit as st
import json
from pathlib import Path

# Page configuration - Set layout to wide for the side-by-side dashboard view
st.set_page_config(
    page_title="Adsparkx AI - Adaptive Support Console",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

from src.config import Config
from src.logger import setup_logger
from src.classifier import PersonaClassifier
from src.rag_pipeline import RAGPipeline
from src.escalator import EscalationManager
from src.generator import ResponseGenerator
from src.exceptions import SupportAgentError

logger = setup_logger("app_ui")

# Custom CSS for Premium Glassmorphism and Modern Typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3, h4 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
    }

    /* Main Title Styling */
    .title-gradient {
        background: linear-gradient(135deg, #FF6B6B 0%, #4D96FF 50%, #6BCB77 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    .subtitle-text {
        color: #64748B;
        font-size: 1.1rem;
        margin-top: 0px;
        margin-bottom: 25px;
    }

    /* Metric Cards Styling */
    .telemetry-card {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 18px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05);
        backdrop-filter: blur(10px);
        margin-bottom: 15px;
    }
    
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .badge-normal {
        background: rgba(107, 203, 119, 0.2);
        color: #2ECC71;
        border: 1px solid rgba(107, 203, 119, 0.4);
    }
    
    .badge-escalated {
        background: rgba(255, 107, 107, 0.2);
        color: #FF4D4D;
        border: 1px solid rgba(255, 107, 107, 0.4);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }

    .source-tag {
        display: inline-block;
        background: rgba(77, 150, 255, 0.15);
        color: #4D96FF;
        border: 1px solid rgba(77, 150, 255, 0.3);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 5px;
        margin-top: 5px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE SETUP -----------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "consecutive_frustrations" not in st.session_state:
    st.session_state.consecutive_frustrations = 0
if "escalated" not in st.session_state:
    st.session_state.escalated = False
if "current_telemetry" not in st.session_state:
    st.session_state.current_telemetry = None

# Handle API Key dynamically for Cloud Deployment
api_key = Config.GEMINI_API_KEY

# Check if user entered key in Streamlit Session State
if "user_gemini_key" in st.session_state and st.session_state.user_gemini_key:
    api_key = st.session_state.user_gemini_key

# Always show API Authentication section in the sidebar
st.sidebar.markdown("### 🔑 API Authentication")

if api_key:
    # Key is loaded (either from .env or UI input)
    masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "••••••••"
    st.sidebar.success(f"Active Key: `{masked_key}`")
    
    # Allow user to update/override the key in the UI if desired
    new_key = st.sidebar.text_input("Update Gemini API Key", type="password", value=api_key, key="gemini_key_input_widget")
    if new_key != api_key:
        st.session_state.user_gemini_key = new_key
        st.rerun()
else:
    # Key is missing - Display mandatory field warning
    st.sidebar.error("🔴 Gemini API Key is Required *")
    key_input = st.sidebar.text_input("Enter Gemini API Key *", type="password", placeholder="AIzaSy...", key="gemini_key_input_widget")
    if key_input:
        st.session_state.user_gemini_key = key_input
        st.rerun()
        
    st.info("⚠️ **Authentication Required**: Please enter a valid Google Gemini API Key in the sidebar to unlock the support agent chat interface.")
    st.stop()

# Set Config API key to active key
Config.GEMINI_API_KEY = api_key

# Initialize classes inside a cached function to avoid re-initializing on every render
@st.cache_resource
def get_services(gemini_api_key: str):
    try:
        # Set config key (ensures it is set inside the cached environment)
        Config.GEMINI_API_KEY = gemini_api_key
        Config.validate()
        
        classifier = PersonaClassifier()
        pipeline = RAGPipeline(force_local=False)
        # Automatic doc ingestion check
        pipeline.ingest_all_documents(force=False)
        escalator = EscalationManager()
        generator = ResponseGenerator()
        return classifier, pipeline, escalator, generator, None
    except Exception as e:
        logger.exception("Error initializing support agent systems")
        return None, None, None, None, str(e)

classifier, pipeline, escalator, generator, init_error = get_services(api_key)

# ----------------- APP HEADER -----------------
col_title, col_status = st.columns([8, 2])
with col_title:
    st.markdown('<div class="title-gradient">Adsparkx AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle-text">Persona-Adaptive Cognitive Support & Agent Handoff Console</div>', unsafe_allow_html=True)

with col_status:
    # Clear console session helper
    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.consecutive_frustrations = 0
        st.session_state.escalated = False
        st.session_state.current_telemetry = None
        st.rerun()

# Check for init error
if init_error:
    st.error(f"🔴 System Initialization Error: {init_error}")
    st.info("💡 Please verify that you have added a valid GEMINI_API_KEY inside your .env file at the root level.")
    st.stop()

# ----------------- DUAL PANEL VIEW -----------------
chat_col, telemetry_col = st.columns([6, 4])

# ================= TELEMETRY SIDE PANEL =================
with telemetry_col:
    st.subheader("📊 System Telemetry & Cognition")
    
    # State widget
    status_class = "badge-escalated" if st.session_state.escalated else "badge-normal"
    status_text = "⚠️ ESCALATED (Human Handoff)" if st.session_state.escalated else "✅ ONLINE (Automated RAG)"
    st.markdown(f'Conversation Status: <span class="status-badge {status_class}">{status_text}</span>', unsafe_allow_html=True)
    st.write(f"⏱️ Consecutive User Frustrations: **{st.session_state.consecutive_frustrations} / {Config.CONSECUTIVE_FRUSTRATION_LIMIT}**")
    
    # Display Current Turn Telemetry
    tel = st.session_state.current_telemetry
    if tel:
        st.markdown('<div class="telemetry-card">', unsafe_allow_html=True)
        st.markdown("### 👤 Persona Classification")
        st.markdown(f"**Identified Persona**: `{tel['persona']}`")
        st.markdown(f"**Sentiment**: `{tel['sentiment']}` | **Is Sensitive**: `{tel['is_sensitive']}`")
        st.write(f"**Reasoning**: *{tel['reasoning']}*")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="telemetry-card">', unsafe_allow_html=True)
        st.markdown("### 🔍 RAG Context Retrieval")
        if tel['context_chunks']:
            st.markdown(f"**Best Similarity Score**: `{tel['best_score']:.4f}`")
            st.write("Retrieved Snippets:")
            for idx, chk in enumerate(tel['context_chunks']):
                st.markdown(f"**{idx+1}. [{chk['source']}]** *(Similarity: {chk['score']:.2f})*")
                st.info(chk['text'])
        else:
            st.markdown("⚠️ *No matching context chunks found in RAG database.*")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display Handoff JSON if escalated
        if tel['handoff']:
            st.markdown('<div class="telemetry-card" style="border: 1px solid rgba(255, 107, 107, 0.4);">', unsafe_allow_html=True)
            st.markdown("<h3 style='color: #FF4D4D;'>🚨 Live Human Handoff Report</h3>", unsafe_allow_html=True)
            st.markdown("**Reason**: " + tel['escalation_reason'])
            st.markdown("**Actionable Handoff JSON Payload**:")
            st.json(tel['handoff'])
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Submit a query in the chat console to analyze the RAG telemetry and cognitive decisions.")

# ================= MAIN CHAT WINDOW =================
with chat_col:
    st.subheader("💬 Support Chat Console")
    
    # Render messages history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # If there's localized escalation tag
            if msg.get("escalated"):
                st.warning("⚠️ Escalated to a human agent.")
                
    # Check if session is already escalated - show blocker
    if st.session_state.escalated:
        st.warning("🔒 This session is escalated to our billing/security supervisor. A live human support representative will respond shortly.")
        st.stop()

    # User chat input
    user_query = st.chat_input("Explain your support request...")

    if user_query:
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})

        # Process through Cognitive Loop
        with st.spinner("Analyzing message & query context..."):
            try:
                # 1. Classification
                classification = classifier.classify(user_query)
                persona = classification.persona
                is_sensitive = classification.is_sensitive
                sentiment = classification.sentiment
                
                # Update consecutive frustration state
                if persona == "Frustrated User" or sentiment == "Negative":
                    st.session_state.consecutive_frustrations += 1
                else:
                    st.session_state.consecutive_frustrations = max(0, st.session_state.consecutive_frustrations - 1)

                # 2. Retrieve Context
                context_chunks = pipeline.retrieve_context(user_query, top_k=3)
                best_score = max([chk["score"] for chk in context_chunks]) if context_chunks else 0.0

                # 3. Check Escalation
                escalation_result = escalator.evaluate(
                    query=user_query,
                    persona_info=classification.model_dump(),
                    context_chunks=context_chunks,
                    consecutive_frustration=st.session_state.consecutive_frustrations
                )
                
                is_escalated = escalation_result["escalated"]
                escalation_reason = escalation_result["reason"]
                handoff_data = escalation_result["handoff_summary"]

                # 4. Generate Telemetry Object
                tel_object = {
                    "persona": persona,
                    "is_sensitive": is_sensitive,
                    "sentiment": sentiment,
                    "reasoning": classification.reasoning,
                    "context_chunks": context_chunks,
                    "best_score": best_score,
                    "escalated": is_escalated,
                    "escalation_reason": escalation_reason,
                    "handoff": handoff_data
                }
                st.session_state.current_telemetry = tel_object

                # 5. Output Response / Action
                if is_escalated:
                    st.session_state.escalated = True
                    response_text = (
                        "I apologize, but this topic requires manual authorization or verification. "
                        "I am escalating your ticket to our billing/security supervisor. "
                        "A live agent will follow up with you directly."
                    )
                    
                    with st.chat_message("assistant"):
                        st.markdown(response_text)
                        st.warning("⚠️ Escalated to a human agent.")
                        
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "escalated": True
                    })
                    st.rerun()
                else:
                    # Generate response via the generator using custom instructions
                    response_text = generator.generate(
                        user_query=user_query,
                        persona=persona,
                        context_chunks=context_chunks
                    )
                    
                    with st.chat_message("assistant"):
                        st.markdown(response_text)
                        
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "escalated": False
                    })
                    st.rerun()

            except Exception as e:
                logger.exception("Error processing chat message")
                st.error(f"Error handling request: {e}")
