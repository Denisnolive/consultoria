import os, io, hashlib
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
os.environ.pop('GOOGLE_CREDENTIALS_JSON', None)

from agno.vectordb.chroma import ChromaDb
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from drive_loader import get_drive_service, list_pdfs, download

vector_db = ChromaDb(collection='pdf_agent', path='tmp/chromadb', persistent_client=True)
knowledge = Knowledge(vector_db=vector_db)
reader = PDFReader()

service = get_drive_service()
files = list_pdfs(service, os.getenv('GOOGLE_DRIVE_FOLDER_ID'))

for file in files:
    print(f"[Drive] Processando: {file['name']}")
    try:
        pdf_bytes = download(service, file['id'])
        documents = reader.read(io.BytesIO(pdf_bytes), name=file['name'])
        if documents:
            content_hash = hashlib.md5(file['id'].encode()).hexdigest()
            vector_db.insert(content_hash, documents)
            print(f"[Drive] OK: {file['name']} ({len(documents)} chunks)")
        else:
            print(f"[Drive] Vazio: {file['name']}")
    except Exception as e:
        import traceback
        print(f"[Drive] ERRO: {file['name']}: {e}")
        traceback.print_exc()

collection = vector_db.client.get_collection('pdf_agent')
print(f"Total de documentos na base: {collection.count()}")
