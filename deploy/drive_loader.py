import io
import os
import json
import tempfile
import hashlib

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# ── SERVICE ─────────────────────────────────────────────────────
def get_drive_service():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if credentials_path and os.path.exists(credentials_path):
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    elif credentials_json:
        credentials_info = json.loads(credentials_json)
        creds = service_account.Credentials.from_service_account_info(
            credentials_info, scopes=SCOPES
        )
    else:
        raise ValueError("Nenhuma credencial Google definida!")

    return build("drive", "v3", credentials=creds)

# ── LISTAGEM ────────────────────────────────────────────────────
def list_pdfs(service, folder_id):
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    result = service.files().list(
        q=query,
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    files = result.get("files", [])
    print(f"[Drive] {len(files)} PDF(s) encontrado(s)")
    return files

# ── DOWNLOAD ────────────────────────────────────────────────────
def download(service, file_id):
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()

# ── SANITIZA METADADOS (remove acentos problemáticos) ────────────
def sanitize_metadata(metadata: dict) -> dict:
    """Garante que todos os valores de metadados são ASCII-safe strings."""
    safe = {}
    for k, v in metadata.items():
        safe_key = str(k).encode("utf-8").decode("utf-8")
        safe_val = str(v).encode("utf-8").decode("utf-8")
        safe[safe_key] = safe_val
    return safe

# ── INGESTÃO DIRETA VIA CHROMADB ─────────────────────────────────
def load_pdfs_from_drive(knowledge, folder_id=None):
    from agno.knowledge.reader.pdf_reader import PDFReader
    from openai import OpenAI

    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    print(f"[Drive] Folder ID: {folder_id}")

    service = get_drive_service()
    files = list_pdfs(service, folder_id)
    if not files:
        print("[Drive] Nenhum PDF encontrado na pasta!")
        return

    chroma_client = knowledge.vector_db.client
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ✅ Recria coleção limpa sem conflito de embedding function
    try:
        chroma_client.delete_collection(name="pdf_agent")
        print("[Drive] 🗑️  Coleção antiga deletada")
    except Exception:
        pass
    collection = chroma_client.create_collection(name="pdf_agent")
    print("[Drive] ✅ Nova coleção criada")

    reader = PDFReader()
    total_chunks = 0

    for file in files:
        print(f"\n[Drive] Processando: {file['name']}")
        tmp_path = None
        try:
            pdf_bytes = download(service, file["id"])
            print(f"[Drive] Download OK: {len(pdf_bytes):,} bytes")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            documents = reader.read(tmp_path)
            if not documents:
                print(f"[Drive] ⚠️  Sem texto extraído — PDF pode ser escaneado")
                continue

            print(f"[Drive] Chunks extraídos: {len(documents)}")

            content_hash = hashlib.md5(file["id"].encode()).hexdigest()

            ids, texts, metadatas = [], [], []
            for i, doc in enumerate(documents):
                doc_id = hashlib.md5(f"{content_hash}_{i}".encode()).hexdigest()
                ids.append(doc_id)
                texts.append(doc.content.replace("\x00", "\ufffd"))
                metadatas.append(sanitize_metadata({
                    "source":       file["name"],
                    "file_id":      file["id"],
                    "content_hash": content_hash,
                    "chunk_index":  str(i),
                }))

            # ✅ Gera embeddings via OpenAI antes de inserir no ChromaDB
            print(f"[Drive] Gerando embeddings para {len(texts)} chunks...")
            response = openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            embeddings = [item.embedding for item in response.data]

            collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )
            total_chunks += len(documents)
            print(f"[Drive] ✅ Indexado: {file['name']} ({len(documents)} chunks)")

        except Exception as e:
            import traceback
            print(f"[Drive] ❌ Erro em {file['name']}: {e}")
            traceback.print_exc()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    print(f"\n[Drive] ✅ Concluído — total de chunks indexados: {total_chunks}")

  