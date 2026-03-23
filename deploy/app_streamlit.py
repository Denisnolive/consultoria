# 1 - IMPORTS ===========================================================
# IMPORTANTE: apply_page_config() deve ser chamada ANTES de qualquer outro
# comando st.* — por isso o import e chamada ficam no topo, separados.

from styles import apply_page_config
apply_page_config()   # ← PRIMEIRA instrução st.* do script

# Demais imports APÓS o set_page_config
import requests
import json
import streamlit as st

from styles import apply_global_styles, render_agent_header

AGENT_ID = "agentepdf"
ENDPOINT = f"https://consultoria-1ulg.onrender.com/agents{AGENT_ID}/runs"

# 2 - Conexão com o Agno (SERVER) =========================================

def get_response_stream(message: str):
    response = requests.post(
        url=ENDPOINT,
        data={"message": message, "stream": "true"},
        stream=True,
    )
    for line in response.iter_lines():
        if line and line.startswith(b"data: "):
            try:
                yield json.loads(line[6:])
            except json.JSONDecodeError:
                continue


# 3 - Layout =============================================================

apply_global_styles()          # injeta o CSS global
render_agent_header(           # header fixo no topo
    agent_name="Consultor",
    agent_description="Especialista em Tasy EMR",
    status="Online",
)

# 3.1 - Histórico ─────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3.2 - Renderiza histórico existente ─────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 3.3 - Input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input("Digite sua mensagem..."):

    # Mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Resposta do assistente (streaming)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        for event in get_response_stream(prompt):
            if event.get("event") == "RunContent":
                chunk = event.get("content", "")
                if chunk:
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")

        placeholder.markdown(full_response)

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
    })
