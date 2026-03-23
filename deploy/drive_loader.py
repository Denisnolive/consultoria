"""
drive_loader.py
---------------
Módulo responsável por listar e baixar PDFs de uma pasta do Google Drive.
Lê os bytes diretamente e usa PDFReader para extrair documentos,
inserindo no knowledge base do Agno via load_documents().

Uso:
    from drive_loader import load_pdfs_from_drive
    load_pdfs_from_drive(knowledge)
"""

import io
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ── Configuração ──────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    """Autentica via Service Account e retorna o client do Drive."""
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado: '{credentials_path}'\n"
            "Certifique-se de que o arquivo JSON da Service Account está na raiz do projeto."
        )

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def list_pdfs_in_folder(service, folder_id: str) -> list[dict]:
    """Lista todos os PDFs de uma pasta do Drive. Retorna lista de {id, name}."""
    query = (
        f"'{folder_id}' in parents "
        "and mimeType='application/pdf' "
        "and trashed=false"
    )
    result = service.files().list(
        q=query,
        fields="files(id, name)",
        orderBy="name"
    ).execute()

    files = result.get("files", [])
    print(f"[Drive] {len(files)} PDF(s) encontrado(s) na pasta.")
    return files


def download_pdf_bytes(service, file_id: str) -> bytes:
    """Faz download de um PDF do Drive e retorna os bytes brutos."""
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def load_pdfs_from_drive(knowledge, folder_id: str | None = None):
    """
    Lista PDFs do Drive, extrai o texto via PDFReader e insere no knowledge
    base do Agno usando load_documents() — sem depender de URL HTTP.

    Parâmetros:
        knowledge  — instância do Knowledge do Agno
        folder_id  — ID da pasta do Drive (usa GOOGLE_DRIVE_FOLDER_ID do .env se None)
    """
    from agno.knowledge.reader.pdf_reader import PDFReader

    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not folder_id:
        raise ValueError(
            "GOOGLE_DRIVE_FOLDER_ID não configurado.\n"
            "Adicione no .env ou passe folder_id= como argumento."
        )

    service  = get_drive_service()
    files    = list_pdfs_in_folder(service, folder_id)
    reader   = PDFReader()
    all_docs = []

    if not files:
        print("[Drive] Nenhum PDF para carregar.")
        return

    for file in files:
        file_name = file["name"]
        file_id   = file["id"]

        try:
            print(f"[Drive] Baixando: {file_name} ...")
            pdf_bytes = download_pdf_bytes(service, file_id)

            # PDFReader aceita BytesIO diretamente
            docs = reader.read(io.BytesIO(pdf_bytes))

            # Injeta metadados em cada chunk de documento
            for doc in docs:
                doc.meta_data = doc.meta_data or {}
                doc.meta_data.update({
                    "source": "Google Drive",
                    "file_name": file_name,
                    "drive_file_id": file_id,
                    "type": "pdf",
                })
            all_docs.extend(docs)
            print(f"[Drive] ✓ Lido: {file_name} ({len(docs)} chunks)")

        except Exception as e:
            print(f"[Drive] ✗ Erro em '{file_name}': {e}")

    if all_docs:
        print(f"[Drive] Inserindo {len(all_docs)} chunks no knowledge base...")
        import hashlib, json
        content_hash = hashlib.md5(json.dumps([d.name for d in all_docs]).encode()).hexdigest()
        if knowledge.vector_db.upsert_available():
            knowledge.vector_db.upsert(content_hash=content_hash, documents=all_docs)
        else:
            knowledge.vector_db.insert(content_hash=content_hash, documents=all_docs)
        print("[Drive] ✓ Todos os documentos inseridos com sucesso.")


async def load_pdfs_from_drive_async(knowledge, folder_id: str | None = None):
    """
    Versão assíncrona — load_documents() é síncrono no Agno,
    compatível com asyncio.run() do app_01.py.
    """
    load_pdfs_from_drive(knowledge, folder_id=folder_id)
