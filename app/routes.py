from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header
from typing import Optional
import hashlib
import logging
import tempfile
import os
import json
import re
from pathlib import Path
from .config import groq_client, MAX_UPLOAD_BYTES, API_KEY
from .db import collection
from .utils import extract_text_from_file, chunk_text, get_document_context

logger = logging.getLogger(__name__)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    # If no API key is configured, we allow requests (local dev default).
    if not API_KEY:
        return
    # When a key is set, clients must send X-API-Key.
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def sanitize_filename(name: str) -> str:
    # Strip directory components and replace unsafe characters.
    # This prevents path traversal like "../../secret".
    base_name = Path(name).name.strip()
    if not base_name:
        raise ValueError("Invalid filename")
    return SAFE_FILENAME_RE.sub("_", base_name)


def build_artifact_filename(filename_base: str, kind: str) -> str:
    # Create a safe, deterministic artifact filename:
    # - sanitize the user-provided name
    # - add a short hash to avoid collisions
    suffix = "_quiz.json" if kind == "quiz" else "_flashcards.json"
    safe_base = sanitize_filename(filename_base)
    digest = hashlib.sha256(filename_base.encode("utf-8")).hexdigest()[:8]
    return f"{safe_base}_{digest}{suffix}"


# Apply API key protection to every route in this file.
router = APIRouter(dependencies=[Depends(require_api_key)])


# Simple in-memory counters (reset on server restart).
metrics_counters = {
    "total_requests": 0,
    "total_tokens_used": 0,
}


# Artifacts storage (data/artifacts/)
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "data" / "artifacts"


def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def save_artifact(filename_base: str, data_obj, kind: str) -> str:
    """
    Save a generated artifact as JSON in data/artifacts/.
    Returns the saved filename.
    kind should be 'quiz' or 'flashcards'.
    """
    ensure_artifacts_dir()
    safe_name = build_artifact_filename(filename_base, kind)
    path = ARTIFACTS_DIR / safe_name
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data_obj, fh, ensure_ascii=False, indent=2)
    return safe_name


@router.get("/ping")
def ping():
    return {"status": "Corpus Forge Engine is online and ready."}


@router.get("/metrics/")
def get_metrics():
    return {
        "total_requests": metrics_counters["total_requests"],
        "total_tokens_used": metrics_counters["total_tokens_used"],
    }


@router.post("/upload/")
async def upload_document(file: UploadFile = File(...)):
    """
    Ingestion pipeline: Takes a file, extracts text, chunks it, and saves the vectors to ChromaDB.
    Includes a try/finally block to guarantee temporary files are wiped even if extraction crashes.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    # File type validation based on extension.
    extension = Path(file.filename).suffix.lower().lstrip(".")
    if extension not in ["txt", "md", "pdf", "py", "js"]:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    temp_path = None
    try:
        # Save to a temporary file on disk so PyMuPDF can read PDFs.
        # We stream the upload in chunks and enforce MAX_UPLOAD_BYTES.
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temp_file:
            temp_path = temp_file.name
            total_bytes = 0
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="File too large. Max upload size is 10 MB.",
                    )
                temp_file.write(chunk)

        raw_text = extract_text_from_file(temp_path, file.filename)
        chunks = chunk_text(raw_text)

        # Anti-duplicate logic: replace existing chunks for the same filename.
        existing_docs = collection.get(where={"filename": file.filename})
        if existing_docs["ids"]:
            collection.delete(where={"filename": file.filename})

        # Process and store each chunk with metadata.
        for i, chunk in enumerate(chunks):
            chunk_id = f"{file.filename}_chunk_{i}"
            collection.add(
                documents=[chunk],
                metadatas=[
                    {"filename": file.filename, "type": file.filename.split(".")[-1]}
                ],
                ids=[chunk_id],
            )

        return {
            "message": f"Successfully ingested {file.filename}",
            "chunks_processed": len(chunks),
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail="Internal server error.")

    finally:
        # HARDENED SECURITY: This always runs, preventing disk bloat during the demo
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/chat/")
async def chat_with_corpus(
    query: str = Form(...),
    audience_level: str = Form("expert"),
    tone: str = Form("professional"),
    filename: Optional[str] = Form(None),
):
    """
    Standard Q&A endpoint. Pulls the top 3 most relevant chunks based on the user's query
    and feeds them to Groq to generate an answer.
    """
    try:
        # 1. Retrieve the most relevant chunks from the vector database.
        if filename:
            results = collection.query(
                query_texts=[query], n_results=3, where={"filename": filename}
            )
        else:
            results = collection.query(query_texts=[query], n_results=3)

        if not results["documents"] or not results["documents"][0]:
            raise HTTPException(
                status_code=404, detail="No relevant context found in the database."
            )

        context = "\n\n---\n\n".join(results["documents"][0])

        # 2. Build the system prompt with audience and tone settings.
        system_prompt = f"""You are Corpus Forge, an AI assistant analyzing a document corpus.
        Use ONLY the provided context to answer the user's query. If the answer is not in the context, say you don't know.
        
        Constraints:
        - Audience Level: {audience_level}
        - Tone: {tone}
        
        CONTEXT:
        {context}
        """

        # 3. Call the Groq-hosted LLM with the context and question.
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,  # Keep it low so it relies on the docs, not its imagination
        )

        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens

        # Return metrics for debugging and demo visibility.
        return {
            "response": chat_completion.choices[0].message.content,
            "metrics": {
                "tokens_used": chat_completion.usage.total_tokens,
                "model": "llama-3.1-8b-instant",
                "retrieved_chunks": len(results["documents"][0]),
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/documents/")
async def list_documents():
    """
    Quick helper for the frontend to know what files are currently available to chat with.
    """
    data = collection.get()
    unique_files = list(set([meta["filename"] for meta in data["metadatas"] if meta]))
    return {"documents": unique_files}


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    """
    Delete all chunks for a given filename from the ChromaDB collection.
    """
    try:
        existing = collection.get(where={"filename": filename})
        if not existing.get("ids"):
            raise HTTPException(status_code=404, detail=f"No data found for {filename}")

        collection.delete(where={"filename": filename})
        return {"message": f"Deleted all chunks for {filename}"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Delete document failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/generate/quiz/")
async def generate_quiz(filename: str = Form(...)):
    """
    Generates a structured JSON quiz.
    The response_format={"type": "json_object"} flag guarantees the frontend can easily map over the data.
    """
    try:
        # Pull the full document (capped) so the model sees the complete content.
        context = get_document_context(filename)

        system_prompt = (
            """You are an expert educator. Based ONLY on the provided context, generate a 5-question multiple-choice quiz.
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
        """
            + context
        )

        # Request strict JSON output so the frontend can parse it reliably.
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens

        quiz = json.loads(chat_completion.choices[0].message.content)
        try:
            save_artifact(filename, quiz, "quiz")
        except Exception:
            # Do not fail the whole request if saving the artifact errors; still return the generated content
            pass

        return quiz
    except HTTPException:
        raise
    except Exception:
        logger.exception("Quiz generation failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/generate/flashcards/")
async def generate_flashcards(filename: str = Form(...)):
    """
    Generates JSON flashcards for studying.
    """
    try:
        # Pull the full document (capped) so the model sees the complete content.
        context = get_document_context(filename)

        system_prompt = (
            """You are an expert tutor. Extract the 5 most important concepts from the provided context and create study flashcards.
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
        """
            + context
        )

        # Request strict JSON output so the frontend can parse it reliably.
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens

        flashcards = json.loads(chat_completion.choices[0].message.content)
        try:
            save_artifact(filename, flashcards, "flashcards")
        except Exception:
            pass

        return flashcards
    except HTTPException:
        raise
    except Exception:
        logger.exception("Flashcards generation failed")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/artifacts/")
async def list_artifacts():
    """List saved artifact filenames."""
    ensure_artifacts_dir()
    files = [p.name for p in ARTIFACTS_DIR.iterdir() if p.is_file()]
    return {"artifacts": sorted(files)}


@router.get("/artifacts/{artifact_name}")
async def get_artifact(artifact_name: str):
    """Return the JSON content of a saved artifact."""
    ensure_artifacts_dir()
    # Use only the base name to avoid path traversal like "../".
    artifact_name = Path(artifact_name).name
    path = ARTIFACTS_DIR / artifact_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.exception("Failed to load artifact")
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/generate/code-review/")
async def generate_code_review(filename: str = Form(...)):
    """
    Generates a structured JSON code review.
    Note: This is designed to work best on ingested .py or .js files, not random PDFs.
    """
    try:
        # Pull the full document (capped) so the model can review all code.
        context = get_document_context(filename)

        system_prompt = (
            """You are a Senior Staff Software Engineer. Perform a code review on the provided context.
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
        """
            + context
        )

        # Request strict JSON output so the frontend can parse it reliably.
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,  # Keep it ultra-low so the code review is strictly analytical
            response_format={"type": "json_object"},
        )

        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens

        return json.loads(chat_completion.choices[0].message.content)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Code review generation failed")
        raise HTTPException(status_code=500, detail="Internal server error.")
