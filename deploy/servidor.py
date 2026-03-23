from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS

import os
from dotenv import load_dotenv, find_dotenv

# ── Drive loader (módulo local) ────────────────────────────────────────────────
from drive_loader import load_pdfs_from_drive

load_dotenv(find_dotenv())

# ── RAG ───────────────────────────────────────────────────────────────────────
vector_db = ChromaDb(collection="pdf_agent", path="tmp/chromadb", persistent_client=True)
knowledge = Knowledge(vector_db=vector_db)

# ── Agent ─────────────────────────────────────────────────────────────────────
db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

agent = Agent(
    id="agentepdf",
    name="Agente de PDF",
    model=OpenAIChat(id="gpt-4o", api_key=os.getenv("OPENAI_API_KEY")),
    db=db,
    knowledge=knowledge,
    enable_user_memories=True,
    instructions="Você deve buscar informações nos documentos PDF disponíveis, não deve apresentar o nome do documento em pdf que foi buscado, não deve dizer que sua fonte é PDF.",
    description="Agente especialista em análise de documentos PDF do Google Drive",
    search_knowledge=True,
    num_history_runs=3,
)

# ── AgentOS ───────────────────────────────────────────────────────────────────
agent_os = AgentOS(
    name="Agente de PDF",
    agents=[agent],
)

app = agent_os.get_app()

# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1. Carrega todos os PDFs da pasta do Drive (síncrono)
    load_pdfs_from_drive(knowledge)

    # 2. Sobe o servidor AgentOS
    agent_os.serve(app="servidor:app", host="localhost", port=7777, reload=True)
