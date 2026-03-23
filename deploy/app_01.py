from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb

from fastapi import FastAPI
import uvicorn
import asyncio

import os
from dotenv import load_dotenv, find_dotenv

# ── Drive loader (módulo local) ────────────────────────────────────────────────
from drive_loader import load_pdfs_from_drive_async

load_dotenv(find_dotenv())

# ── RAG ───────────────────────────────────────────────────────────────────────
vector_db = ChromaDb(collection="pdf_agent", path="tmp/chromadb", persistent_client=True)
knowledge = Knowledge(vector_db=vector_db)

# ── Agent ─────────────────────────────────────────────────────────────────────
db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

agent = Agent(
    name="Agente de PDF",
    model=OpenAIChat(id="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY")),
    db=db,
    knowledge=knowledge,
    instructions="Você deve chamar o usuário de senhor e buscar informações nos documentos PDF disponíveis.",
    description="Agente especialista em análise de documentos PDF do Google Drive",
    search_knowledge=True,
    num_history_runs=3,
    debug_mode=True,
)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Agente de PDF", description="API para responder perguntas sobre PDFs do Drive")

@app.post("/agente_pdf")
def agente_pdf(pergunta: str):
    response = agent.run(pergunta)
    return {"message": response.content}

# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1. Carrega todos os PDFs da pasta do Drive de forma assíncrona
    asyncio.run(load_pdfs_from_drive_async(knowledge))

    # 2. Sobe o servidor FastAPI
    uvicorn.run("app_01:app", host="localhost", port=8000, reload=True)
