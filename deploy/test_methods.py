from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb

vector_db = ChromaDb(collection='pdf_agent', path='tmp/chromadb', persistent_client=True)
knowledge = Knowledge(vector_db=vector_db)

methods = [m for m in dir(knowledge) if not m.startswith('_')]
print('\n'.join(methods))
