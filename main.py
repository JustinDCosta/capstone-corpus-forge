import os
import json
import tempfile
import fitz  # PyMuPDF (much faster than standard pypdf for local RAG)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq

# ==========================================
# 1. INITIALIZATION & SETUP
# ==========================================

# Pull keys from .env so we don't accidentally push secrets to GitHub
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("CRITICAL: GROQ_API_KEY is missing from the .env file. Server cannot start.")

app = FastAPI(title="Corpus Forge API")
groq_client = Groq(api_key=GROQ_API_KEY)

# Allow the frontend (Streamlit, React, etc.) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Fine for local dev, restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up local vector storage. This creates a folder called 'chroma_db' in the repo root.
# We are using sentence-transformers here because it's free, local, and runs fast on CPU.
chroma_client = chromadb.PersistentClient(path="./chroma_db")
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

collection = chroma_client.get_or_create_collection(
    name="corpus_collection",
    embedding_function=sentence_transformer_ef
)


# ==========================================
# 2. CORE UTILITIES
# ==========================================

def extract_text_from_file(file_path: str, filename: str) -> str:
    """
    Handles raw text extraction. Fails gracefully if the file is corrupted.
    """
    ext = filename.split(".")[-1].lower()
    text = ""

    if ext in ["txt", "md", "py", "js"]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read text file: {str(e)}")

    elif ext == "pdf":
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text("text")
                if page_text:
                    text += page_text + "\n"
            doc.close()

            # Catch PDFs that are just scanned images
            if not text.strip():
                raise HTTPException(status_code=400,
                                    detail="PDF is empty or contains only unreadable images. Needs OCR.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please stick to txt, md, py, js, or pdf.")

    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Splits massive documents into smaller pieces. 
    The overlap is crucial so we don't cut a sentence or concept in half right where the AI needs it.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def get_document_context(filename: str) -> str:
    """
    Helper to pull all chunks of a specific file out of the database.
    Used for the advanced generation endpoints.
    """
    doc_data = collection.get(where={"filename": filename})
    if not doc_data['documents']:
        raise HTTPException(status_code=404, detail=f"No data found in DB for {filename}")

    # Combine chunks into one string. 
    # Hard cap at ~24,000 characters to ensure we don't blow past Llama 3's 8k token context window.
    full_text = "\n\n".join(doc_data['documents'])
    return full_text[:24000]


# ==========================================
# 3. STANDARD RAG ENDPOINTS
# ==========================================

@app.get("/ping")
def ping():
    return {"status": "Corpus Forge Engine is online and ready."}


@app.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    """
    Ingestion pipeline: Takes a file, extracts text, chunks it, and saves the vectors to ChromaDB.
    Includes a try/finally block to guarantee temporary files are wiped even if extraction crashes.
    """
    if file.filename.split(".")[-1].lower() not in ["txt", "md", "pdf", "py", "js"]:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    temp_path = None
    try:
        # Save to a temporary file on disk so PyMuPDF can actually read it
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        raw_text = extract_text_from_file(temp_path, file.filename)
        chunks = chunk_text(raw_text)

        # Anti-duplicate logic: If this file is already in the DB, wipe the old chunks first.
        existing_docs = collection.get(where={"filename": file.filename})
        if existing_docs['ids']:
            collection.delete(where={"filename": file.filename})

        # Process and store in Chroma
        for i, chunk in enumerate(chunks):
            chunk_id = f"{file.filename}_chunk_{i}"
            collection.add(
                documents=[chunk],
                metadatas=[{"filename": file.filename, "type": file.filename.split('.')[-1]}],
                ids=[chunk_id]
            )

        return {"message": f"Successfully ingested {file.filename}", "chunks_processed": len(chunks)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # HARDENED SECURITY: This always runs, preventing disk bloat during the demo
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/chat/")
async def chat_with_corpus(
        query: str = Form(...),
        audience_level: str = Form("expert"),
        tone: str = Form("professional")
):
    """
    Standard Q&A endpoint. Pulls the top 3 most relevant chunks based on the user's query
    and feeds them to Groq to generate an answer.
    """
    try:
        # 1. Retrieve the most relevant chunks from the database
        results = collection.query(
            query_texts=[query],
            n_results=3
        )

        if not results['documents'] or not results['documents'][0]:
            raise HTTPException(status_code=404, detail="No relevant context found in the database.")

        context = "\n\n---\n\n".join(results['documents'][0])

        # 2. Build the system prompt using the rubric's Tone/Audience constraints
        system_prompt = f"""You are Corpus Forge, an AI assistant analyzing a document corpus.
        Use ONLY the provided context to answer the user's query. If the answer is not in the context, say you don't know.
        
        Constraints:
        - Audience Level: {audience_level}
        - Tone: {tone}
        
        CONTEXT:
        {context}
        """

        # 3. Call the Llama 3.1 model via Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,  # Keep it low so it relies on the docs, not its imagination
        )

        # We return metrics here for observability (good to show during the demo)
        return {
            "response": chat_completion.choices[0].message.content,
            "metrics": {
                "tokens_used": chat_completion.usage.total_tokens,
                "model": "llama-3.1-8b-instant",
                "retrieved_chunks": len(results['documents'][0])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/")
async def list_documents():
    """
    Quick helper for the frontend to know what files are currently available to chat with.
    """
    data = collection.get()
    unique_files = list(set([meta["filename"] for meta in data["metadatas"] if meta]))
    return {"documents": unique_files}


# ==========================================
# 4. ADVANCED GENERATION ENDPOINTS
# ==========================================

@app.post("/generate/quiz/")
async def generate_quiz(filename: str = Form(...)):
    """
    Generates a structured JSON quiz.
    The response_format={"type": "json_object"} flag guarantees the frontend can easily map over the data.
    """
    try:
        context = get_document_context(filename)

        system_prompt = """You are an expert educator. Based ONLY on the provided context, generate a 5-question multiple-choice quiz.
        You MUST respond in strict JSON format. Do not include any conversational text.
        Use this exact JSON schema:
        {
            "quiz": [
                {
                    "question": "...",
                    "options": ["...", "...", "...", "..."],
                    "correct_answer": "..."
                }
            ]
        }
        
        CONTEXT:
        """ + context

        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/flashcards/")
async def generate_flashcards(filename: str = Form(...)):
    """
    Generates JSON flashcards for studying.
    """
    try:
        context = get_document_context(filename)

        system_prompt = """You are an expert tutor. Extract the 5 most important concepts from the provided context and create study flashcards.
        You MUST respond in strict JSON format. Do not include any conversational text.
        Use this exact JSON schema:
        {
            "flashcards": [
                {
                    "front": "Concept or Term",
                    "back": "Detailed definition or explanation"
                }
            ]
        }
        
        CONTEXT:
        """ + context

        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/code-review/")
async def generate_code_review(filename: str = Form(...)):
    """
    Generates a structured JSON code review.
    Note: This is designed to work best on ingested .py or .js files, not random PDFs.
    """
    try:
        context = get_document_context(filename)

        system_prompt = """You are a Senior Staff Software Engineer. Perform a code review on the provided context.
        Identify bugs, security vulnerabilities, and areas for optimization.
        You MUST respond in strict JSON format. Do not include any conversational text.
        Use this exact JSON schema:
        {
            "review": {
                "summary": "Overall impression...",
                "bugs": ["...", "..."],
                "optimizations": ["...", "..."],
                "security_concerns": ["...", "..."]
            }
        }
        
        CONTEXT:
        """ + context

        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,  # Keep it ultra-low so the code review is strictly analytical
            response_format={"type": "json_object"}
        )

        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. SERVER RUNNER
# ==========================================
if __name__ == "__main__":
    # reload=True ensures the server auto-restarts if we modify this file during local dev.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
