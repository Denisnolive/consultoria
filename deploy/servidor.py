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
OPENAI_API_KEY = OPENAI_API_KEY.encode("ascii", errors="ignore").decode("ascii").strip()

print("==> Iniciando servidor...")
print(f"==> PORT: {os.environ.get('PORT')}")
print(f"==> GOOGLE_CREDENTIALS_JSON definida: {bool(os.environ.get('GOOGLE_CREDENTIALS_JSON'))}")
print(f"==> OPENAI_API_KEY definida: {bool(OPENAI_API_KEY)}")

# ── CREDENCIAIS GOOGLE ───────────────────────────────────────────
google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

if google_credentials_path and os.path.exists(google_credentials_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
    print(f"==> Credencial: arquivo local")
elif google_credentials_json:
    credentials_data = json.loads(google_credentials_json)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
    json.dump(credentials_data, tmp)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    print(f"==> Credencial: variável de ambiente")
else:
    raise ValueError("Nenhuma credencial Google definida!")

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb
from agno.os import AgentOS
from drive_loader import load_pdfs_from_drive, get_drive_service, list_pdfs, download

# ── VECTOR DB ────────────────────────────────────────────────────
vector_db = ChromaDb(
    collection="pdf_agent",
    path="tmp/chromadb",
    persistent_client=True
)
knowledge = Knowledge(vector_db=vector_db)

# ── SINCRONIZAÇÃO INTELIGENTE ─────────────────────────────────────
def sincronizar_base():
    import hashlib
    from agno.knowledge.reader.pdf_reader import PDFReader
    from openai import OpenAI

    print("\n[SYNC] ========== INICIANDO SINCRONIZAÇÃO ==========")

    # ── 1. CONECTA AO CHROMADB ───────────────────────────────────
    chroma_client = vector_db.client
    try:
        collection = chroma_client.get_collection("pdf_agent")
        total_chunks = collection.count()
        print(f"[SYNC] Chunks na base: {total_chunks}")
    except Exception:
        collection = chroma_client.create_collection("pdf_agent")
        total_chunks = 0
        print("[SYNC] Coleção criada do zero")

    # ── 2. VALIDA CHUNKS EXISTENTES ──────────────────────────────
    chunks_validos = 0
    arquivos_na_base = set()

    if total_chunks > 0:
        print("[SYNC] Validando chunks existentes...")
        todos = collection.get(include=["documents", "metadatas"])

        for doc, meta in zip(todos["documents"], todos["metadatas"]):
            # Verifica se chunk tem conteúdo real
            if not doc or len(doc.strip()) < 10:
                continue
            # Verifica se tem metadados mínimos
            if not meta or "file_id" not in meta:
                continue
            chunks_validos += 1
            arquivos_na_base.add(meta["file_id"])

        print(f"[SYNC] Chunks válidos: {chunks_validos} de {total_chunks}")
        print(f"[SYNC] Arquivos distintos na base: {len(arquivos_na_base)}")

        # Se mais de 20% dos chunks são inválidos, reconstrói tudo
        if total_chunks > 0 and (chunks_validos / total_chunks) < 0.8:
            print("[SYNC] ⚠️  Muitos chunks inválidos — reconstruindo base completa")
            chroma_client.delete_collection("pdf_agent")
            collection = chroma_client.create_collection("pdf_agent")
            arquivos_na_base = set()
            chunks_validos = 0

    # ── 3. LISTA ARQUIVOS DO DRIVE ───────────────────────────────
    print("\n[SYNC] Listando arquivos no Google Drive...")
    try:
        service = get_drive_service()
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        arquivos_drive = list_pdfs(service, folder_id)
    except Exception as e:
        print(f"[SYNC] ❌ Erro ao acessar Drive: {e}")
        return

    if not arquivos_drive:
        print("[SYNC] ⚠️  Nenhum PDF encontrado no Drive")
        return

    # ── 4. COMPARA DRIVE vs BASE ─────────────────────────────────
    print("\n[SYNC] Comparando Drive vs Base...")
    ids_drive = {f["id"] for f in arquivos_drive}

    # Arquivos no Drive mas não na base = precisam ser indexados
    novos = [f for f in arquivos_drive if f["id"] not in arquivos_na_base]

    # Arquivos na base mas não no Drive = foram removidos do Drive
    removidos = arquivos_na_base - ids_drive

    print(f"[SYNC] ✅ Já indexados e válidos : {len(arquivos_na_base & ids_drive)}")
    print(f"[SYNC] 🆕 Novos / ausentes na base: {len(novos)}")
    print(f"[SYNC] 🗑️  Removidos do Drive      : {len(removidos)}")

    # ── 5. REMOVE DA BASE O QUE FOI DELETADO NO DRIVE ────────────
    if removidos:
        print("\n[SYNC] Removendo arquivos deletados do Drive...")
        for file_id in removidos:
            try:
                existing = collection.get(where={"file_id": file_id})
                if existing["ids"]:
                    collection.delete(ids=existing["ids"])
                    print(f"[SYNC] 🗑️  Removido: {file_id} ({len(existing['ids'])} chunks)")
            except Exception as e:
                print(f"[SYNC] ❌ Erro ao remover {file_id}: {e}")

    # ── 6. INDEXA ARQUIVOS NOVOS ─────────────────────────────────
    if not novos:
        print("\n[SYNC] ✅ Base já está sincronizada com o Drive!")
        return

    print(f"\n[SYNC] Indexando {len(novos)} arquivo(s) novo(s)...")

    clean_key = OPENAI_API_KEY
    openai_client = OpenAI(api_key=clean_key, max_retries=2)
    reader = PDFReader()
    total_indexados = 0

    for file in novos:
        print(f"\n[SYNC] Processando: {file['name']}")
        tmp_path = None
        try:
            # Download
            pdf_bytes = download(service, file["id"])
            print(f"[SYNC] Download OK: {len(pdf_bytes):,} bytes")

            # Salva temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            # Extrai chunks
            documents = reader.read(tmp_path)
            if not documents:
                print(f"[SYNC] ⚠️  Sem texto extraído — PDF pode ser escaneado")
                continue

            print(f"[SYNC] Chunks extraídos: {len(documents)}")
            print(f"[SYNC] Amostra: {repr(documents[0].content[:150])}")

            # Valida que os chunks têm conteúdo real
            docs_validos = [d for d in documents if d.content and len(d.content.strip()) >= 10]
            if not docs_validos:
                print(f"[SYNC] ⚠️  Todos os chunks estão vazios — pulando")
                continue

            if len(docs_validos) < len(documents):
                print(f"[SYNC] ⚠️  {len(documents) - len(docs_validos)} chunks vazios descartados")

            # Prepara dados
            content_hash = hashlib.md5(file["id"].encode()).hexdigest()
            ids, texts, metadatas = [], [], []

            for i, doc in enumerate(docs_validos):
                doc_id = hashlib.md5(f"{content_hash}_{i}".encode()).hexdigest()
                ids.append(doc_id)
                texts.append(doc.content.replace("\x00", "\ufffd"))
                metadatas.append({
                    "source":       file["name"].encode("utf-8").decode("utf-8"),
                    "file_id":      file["id"],
                    "content_hash": content_hash,
                    "chunk_index":  str(i),
                })

            # Gera embeddings
            print(f"[SYNC] Gerando embeddings para {len(texts)} chunks...")
            response = openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            embeddings = [item.embedding for item in response.data]

            # Insere no ChromaDB
            collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )

            total_indexados += len(docs_validos)
            print(f"[SYNC] ✅ Indexado: {file['name']} ({len(docs_validos)} chunks)")

        except Exception as e:
            import traceback
            print(f"[SYNC] ❌ Erro em {file['name']}: {e}")
            traceback.print_exc()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # ── 7. CONFIRMAÇÃO FINAL ─────────────────────────────────────
    print("\n[SYNC] ========== RESULTADO FINAL ==========")
    count_final = collection.count()
    print(f"[SYNC] Total de chunks na base: {count_final}")
    if count_final > 0:
        sample = collection.get(limit=2, include=["documents", "metadatas"])
        for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
            print(f"[SYNC] Chunk {i+1} | Fonte: {meta.get('source','?')} | Preview: {repr(doc[:100])}")
    print("[SYNC] ==========================================\n")


# ── EXECUTA SINCRONIZAÇÃO ─────────────────────────────────────────
sincronizar_base()

# ── DB DE SESSÃO ─────────────────────────────────────────────────
db = SqliteDb(session_table="agent_session", db_file="tmp/agent.db")

# ── PROMPT ───────────────────────────────────────────────────────
prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "memoria.md")
with open(prompt_path, "r", encoding="utf-8") as f:
    instructions = f.read()

# ── AGENT ────────────────────────────────────────────────────────
agent = Agent(
    id="agentepdf",
    name="Agente PDF",
    model=OpenAIChat(id="gpt-4o", api_key=OPENAI_API_KEY),
    db=db,
    knowledge=knowledge,
    instructions=instructions,
    description="Agente especialista em análise de documentos PDF do Google Drive",
    enable_user_memories=True,
    search_knowledge=True,
    num_history_runs=3,
)

# ── AGENT OS ─────────────────────────────────────────────────────
agent_os = AgentOS(name="Agente PDF", agents=[agent])
app = agent_os.get_app()

# ── SERVIDOR ─────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 10000))
        # Evita reimport do módulo (ex.: "servidor:app"), que pode duplicar
        # inicialização e causar conflito de bind da mesma porta.
        agent_os.serve(app=app, host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        import traceback
        print("ERRO AO INICIAR SERVIDOR:")
        traceback.print_exc()
        raise