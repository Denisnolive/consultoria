import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def get_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Variável obrigatória não definida: {var_name}")
    return value

OPENAI_API_KEY = get_env("OPENAI_API_KEY")
GOOGLE_CREDENTIALS = get_env("GOOGLE_CREDENTIALS_PATH")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS

from drive_loader import load_pdfs_from_drive

# Vector DB
vector_db = ChromaDb(
    collection="pdf_agent",
    path="tmp/chromadb",
    persistent_client=True
)

knowledge = Knowledge(vector_db=vector_db)

# 🔥 Evita reprocessamento
if not os.path.exists("tmp/chromadb"):
    print("[INIT] Carregando PDFs...")
    load_pdfs_from_drive(knowledge)
else:
    print("[INIT] Base já existente")

# DB
db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

# Agent
agent = Agent(
    id="agentepdf",
    name="Agente PDF",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    db=db,
    knowledge=knowledge,
    enable_user_memories=True,
    search_knowledge=True,
    num_history_runs=3,
)

agent_os = AgentOS(name="Agente PDF", agents=[agent])
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="servidor:app", host="0.0.0.0", port=10000, reload=False)