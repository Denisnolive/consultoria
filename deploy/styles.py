import streamlit as st


def apply_page_config():
    st.set_page_config(
        page_title="Consultor IA",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="collapsed",
    )


def apply_global_styles():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Fundo azul claro toda a tela ── */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
.stApp,
body {
    background-color: #ddeeff !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Remove chrome do Streamlit ── */
[data-testid="stSidebar"]           { display: none !important; }
#MainMenu                            { visibility: hidden !important; }
header[data-testid="stHeader"]      { display: none !important; }
footer                               { display: none !important; }
[data-testid="stToolbar"]           { display: none !important; }
[data-testid="stDecoration"]        { display: none !important; }
[data-testid="stStatusWidget"]      { display: none !important; }

/* ── Container central ── */
[data-testid="stMainBlockContainer"] {
    background-color: transparent !important;
    max-width: 820px !important;
    padding: 0 16px 16px 16px !important;
    margin: 0 auto !important;
}

/* ── Balão USUÁRIO ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: #1a6dbd !important;
    border: none !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 12px 16px !important;
    margin: 6px 0 6px 18% !important;
    box-shadow: 0 2px 8px rgba(26,109,189,0.25) !important;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) span,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) div {
    color: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.6 !important;
}

/* ── Balão ASSISTENTE ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: #f0f4f8 !important;
    border: 1px solid #d4e3f0 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 12px 16px !important;
    margin: 6px 18% 6px 0 !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) span,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) li,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) div {
    color: #1a2b3c !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14.5px !important;
    line-height: 1.6 !important;
}

/* ── Oculta avatares padrão ── */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    display: none !important;
}

/* ── Campo de input ── */
[data-testid="stChatInput"] {
    background: #ffffff !important;
    border: 1.5px solid #b8d4ed !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 10px rgba(26,109,189,0.12) !important;
}

[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #1a2b3c !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14.5px !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #8aaec8 !important;
}

[data-testid="stChatInputSubmitButton"] button {
    background: #1a6dbd !important;
    border-radius: 10px !important;
    border: none !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #b0cce8; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


def render_agent_header(
    agent_name: str = "Consultor",
    agent_description: str = "Especialista em Tasy EMR",
    status: str = "Online",
):
    st.markdown(
        f"""<div style="background:rgba(255,255,255,0.92);border-bottom:1px solid #d4e3f0;padding:14px 20px;margin-bottom:12px;display:flex;align-items:center;gap:12px;border-radius:0 0 16px 16px;box-shadow:0 2px 14px rgba(26,109,189,0.10);font-family:'DM Sans',sans-serif;">
<div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#1a6dbd,#4da3e8);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;">🤖</div>
<div style="flex:1;min-width:0;">
<p style="margin:0;font-size:15px;font-weight:600;color:#0d2137;letter-spacing:-0.2px;">{agent_name}</p>
<p style="margin:0;font-size:12px;color:#5a87b0;">{agent_description}</p>
</div>
<div style="display:flex;align-items:center;gap:6px;background:#e8f4e8;border:1px solid #b3dab3;border-radius:20px;padding:4px 12px;flex-shrink:0;">
<div style="width:7px;height:7px;border-radius:50%;background:#2da44e;"></div>
<span style="font-size:12px;color:#1a6b1a;font-weight:500;">{status}</span>
</div>
</div>""",
        unsafe_allow_html=True,
    )
