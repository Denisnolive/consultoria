import os
from pathlib import Path
import logging

from dotenv import find_dotenv, load_dotenv

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.os import AgentOS

from postgres_tools import (
    describe_available_schema,
    list_allowed_tables,
    run_read_only_sql,
    test_postgres_connection,
)

load_dotenv(find_dotenv())

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("consultoria.servidor")


def get_required_env(var_name: str) -> str:
    value = os.getenv(var_name, "").strip()
    if not value:
        raise ValueError(f"Variavel obrigatoria nao definida: {var_name}")
    return value


OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")

BASE_DIR = Path(__file__).resolve().parent
TMP_DIR = BASE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS_DIR = BASE_DIR / "prompts"
PROMPT_PATH = PROMPTS_DIR / "postgres_agent.md"

if not PROMPT_PATH.exists():
    raise FileNotFoundError(
        f"Arquivo de prompt nao encontrado: {PROMPT_PATH}"
    )

LOGGER.info("Iniciando servidor PostgreSQL")
LOGGER.info("PORT definida: %s", bool(os.environ.get("PORT")))
LOGGER.info("OPENAI_API_KEY definida: %s", bool(OPENAI_API_KEY))
LOGGER.info(
    "POSTGRES_SQLALCHEMY_URL definida: %s",
    bool(os.getenv("POSTGRES_SQLALCHEMY_URL")),
)
LOGGER.info("POSTGRES_HOST definido: %s", bool(os.getenv("POSTGRES_HOST")))
LOGGER.info("POSTGRES_DB definido: %s", bool(os.getenv("POSTGRES_DB")))

db = SqliteDb(session_table="agent_session", db_file=str(TMP_DIR / "agent.db"))

instructions = PROMPT_PATH.read_text(encoding="utf-8")

agent = Agent(
    id="agentepostgres",
    name="Agente PostgreSQL",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    db=db,
    instructions=instructions,
    description="Agente especialista em consultas PostgreSQL com foco em dados estruturados do ambiente hospitalar.",
    tools=[
        describe_available_schema,
        list_allowed_tables,
        test_postgres_connection,
        run_read_only_sql,
    ],
    enable_user_memories=True,
    add_history_to_context=True,
    num_history_runs=3,
    search_knowledge=False,
    markdown=True,
    add_datetime_to_context=True,
)

agent_os = AgentOS(name="Agente PostgreSQL", agents=[agent])
app = agent_os.get_app()
LOGGER.info("Aplicacao FastAPI do agente criada com id=%s", agent.id)


@app.middleware("http")
async def log_requests(request, call_next):
    LOGGER.info("HTTP %s %s", request.method, request.url.path)
    response = await call_next(request)
    LOGGER.info(
        "HTTP %s %s -> %s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    LOGGER.info("Servidor pronto para iniciar em 0.0.0.0:%s", port)
    agent_os.serve(app=app, host="0.0.0.0", port=port, reload=False)