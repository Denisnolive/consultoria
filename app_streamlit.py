from pathlib import Path
import json
import logging
import os
import sys

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from styles import apply_page_config

apply_page_config()

import requests
import streamlit as st

from styles import apply_global_styles, render_agent_header

AGENT_ID = "agentepostgres"
BASE_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:10000").rstrip("/")
ENDPOINT = f"{BASE_BACKEND_URL}/agents/{AGENT_ID}/runs"
LOGGER = logging.getLogger("consultoria.app_streamlit")

if not LOGGER.handlers:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def get_response_stream(message: str):
    LOGGER.info("Enviando mensagem ao agente. endpoint=%s", ENDPOINT)
    response = requests.post(
        url=ENDPOINT,
        data={"message": message, "stream": "true"},
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    for line in response.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue

        try:
            payload = line[6:].decode("utf-8")
            event = json.loads(payload)
            yield event
        except (UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.warning("Falha ao decodificar evento SSE do backend")
            continue


apply_global_styles()
render_agent_header(
    agent_name="Consultor",
    agent_description="Especialista em Parâmetros Tasy",
    status="Online",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Digite sua mensagem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        completed_response = ""
        tool_error_message = ""

        try:
            for event in get_response_stream(prompt):
                event_type = event.get("event")
                if event_type == "RunContent":
                    chunk = event.get("content", "")
                    if chunk:
                        full_response += chunk
                        placeholder.markdown(full_response + "▌")
                elif event_type == "RunCompleted":
                    completed_response = event.get("content", "") or ""
                elif event_type == "ToolCallStarted":
                    tool_name = event.get("tool", {}).get("tool_name", "tool")
                    placeholder.info(f"Executando ferramenta: {tool_name}")
                elif event_type == "ToolCallError":
                    tool_name = event.get("tool", {}).get("tool_name", "tool")
                    tool_error_message = event.get("error", "") or "Falha na execucao da ferramenta."
                    LOGGER.error("Ferramenta com erro: %s - %s", tool_name, tool_error_message)

        except requests.RequestException as exc:
            full_response = (
                "Erro ao consultar o backend do agente. "
                f"Verifique a variavel BACKEND_URL e a disponibilidade do servico. Detalhe: {exc}"
            )
            placeholder.error(full_response)
        except Exception as exc:
            full_response = f"Erro inesperado: {exc}"
            placeholder.error(full_response)

        if not full_response and completed_response:
            full_response = completed_response

        if not full_response and tool_error_message:
            full_response = f"Erro ao executar consulta/ferramenta: {tool_error_message}"

        if not full_response:
            full_response = "O agente nao retornou conteudo nesta execucao."
            placeholder.warning(full_response)
        elif not full_response.startswith("Erro"):
            placeholder.markdown(full_response)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": full_response,
        }
    )