import io
import os
import hashlib
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# ── SERVICE ─────────────────────────────────────────────────────
# credenciais
def get_drive_service():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if credentials_path and os.path.exists(credentials_path):
        # Ambiente local — usa o arquivo diretamente
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    elif credentials_json:
        # Produção (Render) — usa o conteúdo JSON da variável de ambiente
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

# ── INGESTÃO OTIMIZADA ─────────────────────────────────────────

def load_pdfs_from_drive(knowledge, folder_id=None):
    from agno.knowledge.reader.pdf_reader import PDFReader
    import hashlib

    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    print(f"[Drive] Folder ID: {folder_id}")

    service = get_drive_service()
    print(f"[Drive] Serviço criado com sucesso")

    files = list_pdfs(service, folder_id)
    print(f"[Drive] Arquivos encontrados: {len(files)}")

    if not files:
        print("[Drive] Nenhum PDF encontrado na pasta!")
        return

    reader = PDFReader()

    for file in files:
        print(f"[Drive] Processando: {file['name']}")
        try:
            pdf_bytes = download(service, file["id"])
            documents = reader.read(io.BytesIO(pdf_bytes), name=file["name"])
            if documents:
                content_hash = hashlib.md5(file["id"].encode()).hexdigest()
                knowledge.vector_db.insert(content_hash, documents)
                print(f"[Drive] ✅ Carregado: {file['name']} ({len(documents)} chunks)")
            else:
                print(f"[Drive] ⚠️ Vazio: {file['name']}")
        except Exception as e:
            print(f"[Drive] ❌ Erro: {file['name']}: {e}")

    print("[Embedding] Concluído com sucesso")