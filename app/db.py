import chromadb
from chromadb.utils import embedding_functions

# Create a local, persistent vector database.
# This stores embeddings on disk in ./chroma_db so data survives restarts.
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Convert text chunks into numeric vectors so we can search by meaning.
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# One collection holds all chunks with their metadata.
collection = chroma_client.get_or_create_collection(
    name="corpus_collection", embedding_function=sentence_transformer_ef
)
