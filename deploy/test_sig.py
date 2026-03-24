from agno.vectordb.chroma import ChromaDb
import inspect
vector_db = ChromaDb(collection='pdf_agent', path='tmp/chromadb', persistent_client=True)
print(inspect.signature(vector_db.insert))
