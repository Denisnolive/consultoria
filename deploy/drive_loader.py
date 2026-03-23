import io
import os
import hashlib
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# ── SERVICE ─────────────────────────────────────────────────────

def get_drive_service():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Credencial não encontrada: {credentials_path}")

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )

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

    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    service = get_drive_service()
    files = list_pdfs(service, folder_id)

    if not files:
        print("[Embedding] Concluído com sucesso")