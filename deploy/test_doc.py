import os, io
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

# Testa apenas o primeiro PDF
file = files[0]
print(f"Testando: {file['name']}")
pdf_bytes = download(service, file['id'])
documents = reader.read(io.BytesIO(pdf_bytes), name=file['name'])
print(f"Total de chunks: {len(documents)}")
print(f"Tipo do primeiro documento: {type(documents[0])}")
print(f"Atributos: {[a for a in dir(documents[0]) if not a.startswith('_')]}")
print(f"Conteudo: {documents[0]}")
