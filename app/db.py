import chromadb
from chromadb.utils import embedding_functions

# Set up local vector storage. This creates a folder called 'chroma_db' in the repo root.
chroma_client = chromadb.PersistentClient(path="./chroma_db")
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = chroma_client.get_or_create_collection(
    name="corpus_collection", embedding_function=sentence_transformer_ef
)
