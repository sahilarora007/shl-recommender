import streamlit as st
import requests
import json
import time
from datetime import datetime

# ─── Page Config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="SHL Assessment Advisor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = "http://localhost:8000"

TEST_TYPE_META = {
    "A": {"label": "Ability & Aptitude",           "color": "#3B82F6", "icon": "📊"},
    "B": {"label": "Biodata & Situational",         "color": "#8B5CF6", "icon": "📋"},
    "C": {"label": "Competencies",                  "color": "#10B981", "icon": "🏆"},
    "D": {"label": "Development & 360",             "color": "#F59E0B", "icon": "🔄"},
    "E": {"label": "Assessment Exercises",          "color": "#EF4444", "icon": "✏️"},
    "K": {"label": "Knowledge & Skills",            "color": "#06B6D4", "icon": "💡"},
    "O": {"label": "Occupational Personality",      "color": "#EC4899", "icon": "🧠"},
    "P": {"label": "Personality & Behavior",        "color": "#F97316", "icon": "👤"},
    "S": {"label": "Simulations",                   "color": "#6366F1", "icon": "🖥️"},
}

INTENT_META = {
    "VAGUE":    {"label": "Clarifying",    "color": "#F59E0B", "desc": "Gathering more context from the user"},
    "SPECIFIC": {"label": "Recommending",  "color": "#10B981", "desc": "Enough context to run retrieval & recommend"},
    "REFINE":   {"label": "Refining",      "color": "#3B82F6", "desc": "Updating recommendations with new constraints"},
    "COMPARE":  {"label": "Comparing",     "color": "#8B5CF6", "desc": "Comparing named assessments from catalog"},
    "OFF_TOPIC":{"label": "Refusing",      "color": "#EF4444", "desc": "Out of scope — politely refusing"},
}

# ─── Styling ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Hide default Streamlit elements */
#MainMenu, footer, header { visibility: hidden; }

/* Dark background */
.stApp { background: #0F1117; }

/* Chat messages */
.user-msg {
    background: linear-gradient(135deg, #1E3A5F, #1a2f4e);
    border: 1px solid #2d4a6e;
    border-radius: 18px 18px 4px 18px;
    padding: 14px 18px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    color: #E2E8F0;
    font-size: 15px;
    line-height: 1.6;
}

.assistant-msg {
    background: #1E2130;
    border: 1px solid #2D3748;
    border-radius: 18px 18px 18px 4px;
    padding: 14px 18px;
    margin: 8px 0;
    max-width: 85%;
    color: #E2E8F0;
    font-size: 15px;
    line-height: 1.6;
}

.msg-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
    opacity: 0.6;
}

/* Recommendation card */
.rec-card {
    background: linear-gradient(135deg, #1A2332, #1E2A3A);
    border: 1px solid #2D4A6E;
    border-left: 4px solid;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    transition: all 0.2s ease;
}
.rec-card:hover { transform: translateX(4px); border-color: #3B82F6; }
.rec-name {
    font-weight: 600;
    font-size: 15px;
    color: #F1F5F9;
    margin-bottom: 6px;
}
.rec-type-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}
.rec-link {
    font-size: 12px;
    color: #60A5FA;
    text-decoration: none;
}

/* Pipeline step */
.pipeline-step {
    background: #1A1F2E;
    border: 1px solid #2D3748;
    border-radius: 10px;
    padding: 12px 14px;
    margin: 6px 0;
    position: relative;
}
.pipeline-step.active {
    border-color: #10B981;
    background: linear-gradient(135deg, #0D2B1F, #1A2E22);
}
.pipeline-step.pending { opacity: 0.4; }
.step-label {
    font-size: 12px;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.step-value {
    font-size: 13px;
    color: #E2E8F0;
    margin-top: 3px;
    font-weight: 500;
}

/* Turn counter */
.turn-counter {
    background: linear-gradient(135deg, #1E3A5F, #1a2f4e);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
    margin: 8px 0;
}
.turn-number { font-size: 32px; font-weight: 700; color: #60A5FA; }
.turn-label  { font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.1em; }

/* Green SHL accent */
.shl-green { color: #22C55E; }

/* Input styling */
.stTextInput input {
    background: #1E2130 !important;
    border: 1px solid #374151 !important;
    border-radius: 12px !important;
    color: #F1F5F9 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 15px !important;
    padding: 12px 16px !important;
}
.stTextInput input:focus { border-color: #22C55E !important; box-shadow: 0 0 0 2px rgba(34,197,94,0.15) !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0D1117;
    border-right: 1px solid #1E2130;
}

/* Buttons */
.stButton button {
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}

/* Status dot */
.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
}
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pipeline_log" not in st.session_state:
    st.session_state.pipeline_log = []
if "last_intent" not in st.session_state:
    st.session_state.last_intent = None
if "conversation_ended" not in st.session_state:
    st.session_state.conversation_ended = False
if "total_recs" not in st.session_state:
    st.session_state.total_recs = 0

# ─── Helpers ───────────────────────────────────────────────────────
def get_health():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.status_code == 200
    except:
        return False

def send_message(messages: list) -> dict:
    payload = {"messages": [{"role": m["role"], "content": m["content"]} for m in messages]}
    r = requests.post(f"{API_URL}/chat", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def render_recommendation(rec: dict, idx: int):
    t = rec.get("test_type", "K")
    meta = TEST_TYPE_META.get(t, TEST_TYPE_META["K"])
    color = meta["color"]
    icon  = meta["icon"]
    label = meta["label"]
    name  = rec.get("name", "")
    url   = rec.get("url", "#")

    st.markdown(f"""
    <div class="rec-card" style="border-left-color: {color};">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
            <span style="font-size:20px;">{icon}</span>
            <div>
                <div class="rec-name">{idx}. {name}</div>
                <span class="rec-type-badge" style="background:{color}22; color:{color};">{t} · {label}</span>
            </div>
        </div>
        <a class="rec-link" href="{url}" target="_blank">↗ View on SHL Catalog</a>
    </div>
    """, unsafe_allow_html=True)

def render_pipeline_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Agent Pipeline")
    st.sidebar.caption("What happens on each turn")

    steps = [
        ("1. Refusal Filter",   "Keyword scan before any LLM call",                  True),
        ("2. Intent Classify",  "LLM → VAGUE / SPECIFIC / REFINE / COMPARE / OFF_TOPIC", True),
        ("3. Context Extract",  "LLM → structured JSON: role, seniority, skills",     True),
        ("4. FAISS Retrieval",  "Gemini embeddings + cosine search → top-15 matches", True),
        ("5. LLM Re-rank",      "Llama-3.3-70b selects best 1–10 from candidates",    True),
        ("6. URL Post-filter",  "Python drops any URL not in catalog.json",           True),
    ]
    for label, desc, active in steps:
        css = "active" if active else "pending"
        st.sidebar.markdown(f"""
        <div class="pipeline-step {css}">
            <div class="step-label">{label}</div>
            <div class="step-value" style="font-size:11px; color:#64748B;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.last_intent:
        intent = st.session_state.last_intent
        meta   = INTENT_META.get(intent, {"label": intent, "color": "#64748B", "desc": ""})
        st.sidebar.markdown(f"""
        <div style="margin-top:12px; padding:12px; background:#1A1F2E; border:1px solid {meta['color']}44; border-radius:10px;">
            <div style="font-size:11px; color:#64748B; text-transform:uppercase; letter-spacing:0.08em;">Last Intent</div>
            <div style="color:{meta['color']}; font-weight:700; font-size:14px; margin-top:4px;">{meta['label']}</div>
            <div style="color:#64748B; font-size:11px; margin-top:2px;">{meta['desc']}</div>
        </div>
        """, unsafe_allow_html=True)

def render_session_stats():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📈 Session Stats")
    n_turns = len(st.session_state.messages)
    budget_pct = min(int((n_turns / 8) * 100), 100)
    bar_color = "#22C55E" if n_turns < 6 else ("#F59E0B" if n_turns < 8 else "#EF4444")

    st.sidebar.markdown(f"""
    <div class="turn-counter">
        <div class="turn-number" style="color:{bar_color};">{n_turns}</div>
        <div class="turn-label">Turns used of 8 max</div>
        <div style="background:#1E2130; border-radius:4px; height:6px; margin-top:8px;">
            <div style="background:{bar_color}; border-radius:4px; height:6px; width:{budget_pct}%; transition:width 0.5s;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Recommendations", st.session_state.total_recs)
    with col2:
        catalog_size = 0
        try:
            with open("catalog.json") as f:
                catalog_size = len(json.load(f))
        except:
            pass
        st.metric("Catalog Size", catalog_size)

def render_tech_stack():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 Tech Stack")
    stack_items = [
        ("FastAPI",             "REST API layer",                "#EF4444"),
        ("Groq Llama-3.3-70b", "LLM generation",                "#F97316"),
        ("Gemini Embedding-2",  "Vector embeddings",             "#3B82F6"),
        ("FAISS IndexFlatIP",   "Cosine similarity search",      "#8B5CF6"),
        ("Pydantic v2",         "Schema validation",             "#10B981"),
        ("Streamlit",           "This interface",                "#FF4B4B"),
    ]
    for name, role, color in stack_items:
        st.sidebar.markdown(f"""
        <div style="display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #1E2130;">
            <div style="width:8px; height:8px; border-radius:50%; background:{color}; flex-shrink:0;"></div>
            <div>
                <div style="font-size:12px; font-weight:600; color:#E2E8F0;">{name}</div>
                <div style="font-size:10px; color:#64748B;">{role}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ─── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    # Header
    st.markdown("""
    <div style="padding: 20px 0 10px 0;">
        <div style="font-size:28px; font-weight:800; color:#22C55E; letter-spacing:-0.5px;">SHL.</div>
        <div style="font-size:13px; color:#64748B; margin-top:2px;">Conversational Assessment Advisor</div>
    </div>
    """, unsafe_allow_html=True)

    # API status
    healthy = get_health()
    dot_color = "#22C55E" if healthy else "#EF4444"
    status_text = "API Online" if healthy else "API Offline"
    st.markdown(f"""
    <div style="padding:8px 12px; background:#1A1F2E; border-radius:8px; margin-bottom:8px;">
        <span class="status-dot" style="background:{dot_color};"></span>
        <span style="font-size:12px; color:#94A3B8;">{status_text}</span>
        <span style="float:right; font-size:11px; color:#475569;">localhost:8000</span>
    </div>
    """, unsafe_allow_html=True)

    if not healthy:
        st.error("Start the API: `uvicorn main:app --reload`")

    # Reset
    if st.button("🔄  New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pipeline_log = []
        st.session_state.last_intent = None
        st.session_state.conversation_ended = False
        st.session_state.total_recs = 0
        st.rerun()

    render_pipeline_sidebar()
    render_session_stats()
    render_tech_stack()

    st.sidebar.markdown("---")
    st.sidebar.caption("Built for SHL Labs · AI Intern Assignment 2026")

# ─── Main Area ─────────────────────────────────────────────────────
# Header
st.markdown("""
<div style="padding: 24px 0 8px 0; border-bottom: 1px solid #1E2130; margin-bottom: 24px;">
    <div style="display:flex; align-items:center; gap:16px;">
        <div>
            <h1 style="margin:0; font-size:24px; font-weight:700; color:#F1F5F9;">
                Assessment Advisor
            </h1>
            <p style="margin:4px 0 0 0; font-size:14px; color:#64748B;">
                Describe the role you're hiring for — I'll find the right SHL assessments from the live catalog.
            </p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Example prompts (only on empty state)
if not st.session_state.messages:
    st.markdown("#### Try asking about...")
    examples = [
        ("💻", "Java backend developer, mid-level", "Software Engineering"),
        ("📊", "Senior data analyst with SQL skills", "Analytics"),
        ("🤝", "Entry-level sales rep, customer-facing", "Sales"),
        ("👔", "Executive leadership potential assessment", "Leadership"),
    ]
    cols = st.columns(2)
    for i, (icon, text, category) in enumerate(examples):
        with cols[i % 2]:
            if st.button(f"{icon} {text}", key=f"ex_{i}", use_container_width=True,
                         help=f"Category: {category}"):
                st.session_state.messages.append({"role": "user", "content": text})
                st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

# Chat history
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="display:flex; justify-content:flex-end; margin:8px 0;">
                <div class="user-msg">
                    <div class="msg-label" style="color:#60A5FA;">You</div>
                    {msg["content"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="margin:8px 0;">
                <div class="assistant-msg">
                    <div class="msg-label" style="color:#22C55E;">SHL Advisor</div>
                    {msg.get("reply", msg.get("content", ""))}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Recommendations
            recs = msg.get("recommendations", [])
            if recs:
                st.markdown(f"<div style='padding: 0 0 4px 8px; font-size:12px; color:#64748B; font-weight:600; letter-spacing:0.08em; text-transform:uppercase;'>Recommended Assessments ({len(recs)})</div>", unsafe_allow_html=True)
                for idx, rec in enumerate(recs, 1):
                    render_recommendation(rec, idx)

            if msg.get("end_of_conversation"):
                st.markdown("""
                <div style="padding:10px 16px; background:#0D2B1F; border:1px solid #22C55E44; border-radius:10px; margin-top:8px;">
                    <span style="color:#22C55E; font-size:13px; font-weight:600;">✓ Conversation complete</span>
                    <span style="color:#64748B; font-size:12px; margin-left:8px;">Use the button above to start a new session.</span>
                </div>
                """, unsafe_allow_html=True)

# ─── Input ─────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

if st.session_state.conversation_ended:
    st.info("This conversation is complete. Click **New Conversation** in the sidebar to start over.")
else:
    with st.form("chat_form", clear_on_submit=True):
        cols = st.columns([6, 1])
        with cols[0]:
            user_input = st.text_input(
                "Message",
                placeholder="Describe the role, seniority, skills, or ask to compare assessments...",
                label_visibility="collapsed",
                key="input_box",
            )
        with cols[1]:
            submitted = st.form_submit_button("Send →", use_container_width=True, type="primary")

    if submitted and user_input.strip():
        if not healthy:
            st.error("API is offline. Please start `uvicorn main:app --reload` first.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input.strip()})

            with st.spinner("Thinking..."):
                try:
                    t0 = time.time()
                    response = send_message(st.session_state.messages)
                    latency = round(time.time() - t0, 2)

                    assistant_msg = {
                        "role": "assistant",
                        "reply": response.get("reply", ""),
                        "content": response.get("reply", ""),
                        "recommendations": response.get("recommendations", []),
                        "end_of_conversation": response.get("end_of_conversation", False),
                    }
                    st.session_state.messages.append(assistant_msg)
                    st.session_state.total_recs += len(assistant_msg["recommendations"])

                    if assistant_msg["end_of_conversation"]:
                        st.session_state.conversation_ended = True

                    # Log pipeline event
                    st.session_state.pipeline_log.append({
                        "turn": len(st.session_state.messages) // 2,
                        "latency": latency,
                        "recs": len(assistant_msg["recommendations"]),
                        "ts": datetime.now().strftime("%H:%M:%S"),
                    })

                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the API. Make sure `uvicorn main:app --reload` is running.")
                    st.session_state.messages.pop()
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.session_state.messages.pop()

            st.rerun()

# ─── Pipeline Log (collapsible) ────────────────────────────────────
if st.session_state.pipeline_log:
    with st.expander("📜 Pipeline Log (this session)", expanded=False):
        log_data = []
        for entry in st.session_state.pipeline_log:
            log_data.append({
                "Turn":        entry["turn"],
                "Time":        entry["ts"],
                "Latency (s)": entry["latency"],
                "Recs":        entry["recs"],
            })
        st.dataframe(log_data, use_container_width=True, hide_index=True)
