import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
SCHEMA_CONTEXT_PATH = PROMPTS_DIR / "schema_context.md"
DEFAULT_MAX_ROWS = 50
LOGGER = logging.getLogger("consultoria.postgres_tools")

load_dotenv(find_dotenv())

FORBIDDEN_SQL_PATTERNS = (
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bmerge\b",
    r"\balter\b",
    r"\bdrop\b",
    r"\btruncate\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bcommit\b",
    r"\brollback\b",
    r"\bdo\b",
    r"\bcreate\b",
    r"\bcall\b",
)


def _get_int_env(var_name: str, default: int) -> int:
    raw_value = os.getenv(var_name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Valor invalido para {var_name}: {raw_value}") from exc


def _get_max_rows() -> int:
    max_rows = _get_int_env("POSTGRES_MAX_ROWS", DEFAULT_MAX_ROWS)
    return min(max(max_rows, 1), 200)


def _get_allowed_tables() -> list[str]:
    raw_tables = os.getenv("POSTGRES_ALLOWED_TABLES", "").strip()
    if not raw_tables:
        return []
    return [item.strip().upper() for item in raw_tables.split(",") if item.strip()]


def _read_schema_context() -> str:
    if not SCHEMA_CONTEXT_PATH.exists():
        return (
            "Nenhum esquema detalhado foi cadastrado ainda. "
            "Preencha prompts/schema_context.md com tabelas, colunas, joins e regras de negocio."
        )
    content = SCHEMA_CONTEXT_PATH.read_text(encoding="utf-8").strip()
    return content or "Schema context vazio."


def _build_connection_url() -> str:
    explicit_url = os.getenv("POSTGRES_SQLALCHEMY_URL", "").strip()
    if explicit_url:
        return explicit_url

    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "").strip()
    host = os.getenv("POSTGRES_HOST", "").strip()
    port = os.getenv("POSTGRES_PORT", "5432").strip()
    database = os.getenv("POSTGRES_DB", "").strip()
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer").strip()

    if user and password and host and database:
        return (
            "postgresql+psycopg://"
            f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
            f"?sslmode={quote_plus(sslmode)}"
        )

    raise ValueError(
        "Configure POSTGRES_SQLALCHEMY_URL ou informe POSTGRES_USER, POSTGRES_PASSWORD, "
        "POSTGRES_HOST e POSTGRES_DB."
    )


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    return create_engine(
        _build_connection_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def _normalize_sql(query: str) -> str:
    sql = query.strip()
    if not sql:
        raise ValueError("A consulta SQL nao pode ser vazia.")
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    if ";" in sql:
        raise ValueError("Nao envie multiplas instrucoes SQL na mesma chamada.")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise ValueError("Comentarios SQL nao sao permitidos.")
    return sql


def _validate_statement_type(sql: str) -> None:
    lowered = sql.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Apenas consultas SELECT ou WITH ... SELECT sao permitidas.")
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, lowered):
            raise ValueError("A consulta contem operacoes nao permitidas. Use somente leitura.")


def _extract_table_names(sql: str) -> list[str]:
    candidates = re.findall(r"\b(?:from|join)\s+([A-Za-z0-9_.$\"]+)", sql, flags=re.IGNORECASE)
    table_names: list[str] = []
    for candidate in candidates:
        clean_name = candidate.strip().replace('"', "")
        if clean_name:
            table_names.append(clean_name.upper())
    return table_names


def _validate_allowed_tables(sql: str) -> None:
    allowed_tables = _get_allowed_tables()
    if not allowed_tables:
        return

    referenced_tables = _extract_table_names(sql)
    if not referenced_tables:
        raise ValueError(
            "Nao foi possivel identificar as tabelas referenciadas. "
            "Use nomes de tabelas explicitamente no FROM/JOIN."
        )

    normalized_allowed = set(allowed_tables)
    for table_name in referenced_tables:
        unqualified_name = table_name.split(".")[-1]
        if table_name not in normalized_allowed and unqualified_name not in normalized_allowed:
            raise ValueError(
                f"Tabela nao permitida na consulta: {table_name}. "
                "Use apenas as tabelas liberadas no catalogo."
            )


def _apply_limit(sql: str, max_rows: int) -> str:
    lowered = sql.lower()
    if re.search(r"\blimit\s+\d+\b", lowered):
        return sql
    return f"{sql}\nLIMIT {max_rows}"


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def describe_available_schema() -> str:
    """Retorna o contexto do esquema PostgreSQL e as regras de uso do catalogo."""
    payload = {
        "allowed_tables": _get_allowed_tables(),
        "max_rows_per_query": _get_max_rows(),
        "schema_context": _read_schema_context(),
        "notes": [
            "Use apenas tabelas e colunas presentes no contexto.",
            "Se faltar identificador do paciente, atendimento ou periodo, peca a informacao.",
            "Prefira consultas agregadas e objetivas antes de consultas amplas.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def list_allowed_tables() -> str:
    """Lista as tabelas autorizadas para consulta."""
    allowed_tables = _get_allowed_tables()
    if not allowed_tables:
        return "Nenhuma tabela foi configurada em POSTGRES_ALLOWED_TABLES."
    return "\n".join(allowed_tables)


def test_postgres_connection() -> str:
    """Valida a conectividade basica com o PostgreSQL usando SELECT 1 AS status."""
    LOGGER.info("Testando conectividade com PostgreSQL")
    engine = _get_engine()
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1 AS status"))
        row = result.fetchone()
    LOGGER.info("Conectividade com PostgreSQL validada com sucesso")
    return json.dumps(
        {
            "status": "ok",
            "probe_query": "SELECT 1 AS status",
            "result": dict(row._mapping) if row else {},
        },
        ensure_ascii=False,
        indent=2,
    )


def run_read_only_sql(query: str) -> str:
    """Executa uma consulta PostgreSQL somente leitura e retorna linhas serializadas em JSON."""
    LOGGER.info("Recebida consulta para execucao", extra={"query_preview": query[:300]})
    sql = _normalize_sql(query)
    _validate_statement_type(sql)
    _validate_allowed_tables(sql)

    max_rows = _get_max_rows()
    executable_sql = _apply_limit(sql, max_rows=max_rows)

    engine = _get_engine()
    with engine.connect() as connection:
        LOGGER.info("Executando SQL", extra={"sql": executable_sql})
        result = connection.execute(text(executable_sql))
        rows = result.fetchmany(max_rows + 1)
        columns = list(result.keys())

    truncated = len(rows) > max_rows
    visible_rows = rows[:max_rows]
    serialized_rows = []
    for row in visible_rows:
        serialized_rows.append({key: _serialize_value(value) for key, value in row._mapping.items()})

    payload = {
        "sql_executed": executable_sql,
        "columns": columns,
        "row_count": len(visible_rows),
        "truncated": truncated,
        "rows": serialized_rows,
    }
    LOGGER.info(
        "Consulta finalizada",
        extra={
            "row_count": len(visible_rows),
            "truncated": truncated,
            "columns": ",".join(columns),
        },
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
