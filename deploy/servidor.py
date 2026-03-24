import os
import json
import tempfile
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

def get_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Variável obrigatória não definida: {var_name}")
    return value

OPENAI_API_KEY = get_env("OPENAI_API_KEY")

print("==> Iniciando servidor...")
print(f"==> PORT: {os.environ.get('PORT')}")
print(f"==> GOOGLE_CREDENTIALS_JSON definida: {bool(os.environ.get('GOOGLE_CREDENTIALS_JSON'))}")
print(f"==> OPENAI_API_KEY definida: {bool(os.environ.get('OPENAI_API_KEY'))}")

# Suporte local (arquivo) e produção (JSON na variável de ambiente)
google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

if google_credentials_path:
    # Ambiente local — usa o arquivo diretamente
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
elif google_credentials_json:
    # Produção (Render) — cria arquivo temporário com o conteúdo JSON
    credentials_data = json.loads(google_credentials_json)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    json.dump(credentials_data, tmp)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
else:
    raise ValueError("Nenhuma credencial Google definida!")

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

# Verifica se a base tem documentos carregados
def base_tem_documentos() -> bool:
    try:
        collection = vector_db.client.get_collection("pdf_agent")
        count = collection.count()
        print(f"[INIT] Documentos na base: {count}")
        return count > 0
    except Exception as e:
        print(f"[INIT] Coleção não encontrada: {e}")
        return False

if base_tem_documentos():
    print("[INIT] Base já existente com dados, pulando carregamento.")
else:
    print("[INIT] Base vazia, carregando PDFs...")
    load_pdfs_from_drive(knowledge)


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
    try:
        port = int(os.environ.get("PORT", 10000))
        agent_os.serve(app="servidor:app", host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        import traceback
        print("ERRO AO INICIAR SERVIDOR:")
        traceback.print_exc()
        raise