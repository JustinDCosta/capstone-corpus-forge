from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import tempfile
import os
import json
from pathlib import Path
from .config import groq_client
from .db import collection
from .utils import extract_text_from_file, chunk_text, get_document_context


router = APIRouter()


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
    suffix = "_quiz.json" if kind == "quiz" else "_flashcards.json"
    safe_name = f"{filename_base}{suffix}"
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
    if file.filename.split(".")[-1].lower() not in ["txt", "md", "pdf", "py", "js"]:
        raise HTTPException(status_code=400, detail="Invalid file type.")


    temp_path = None
    try:
        # Save to a temporary file on disk so PyMuPDF can actually read it
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file.filename.split('.')[-1]}"
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name


        raw_text = extract_text_from_file(temp_path, file.filename)
        chunks = chunk_text(raw_text)


        # Anti-duplicate logic: If this file is already in the DB, wipe the old chunks first.
        existing_docs = collection.get(where={"filename": file.filename})
        if existing_docs["ids"]:
            collection.delete(where={"filename": file.filename})


        # Process and store in Chroma
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


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    finally:
        # HARDENED SECURITY: This always runs, preventing disk bloat during the demo
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)



@router.post("/chat/")
async def chat_with_corpus(
    query: str = Form(...),
    audience_level: str = Form("expert"),
    tone: str = Form("professional"),
):
    """
    Standard Q&A endpoint. Pulls the top 3 most relevant chunks based on the user's query
    and feeds them to Groq to generate an answer.
    """
    try:
        # 1. Retrieve the most relevant chunks from the database
        results = collection.query(query_texts=[query], n_results=3)


        if not results["documents"] or not results["documents"][0]:
            raise HTTPException(
                status_code=404, detail="No relevant context found in the database."
            )


        context = "\n\n---\n\n".join(results["documents"][0])


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
                {"role": "user", "content": query},
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,  # Keep it low so it relies on the docs, not its imagination
        )


        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens


        # We return metrics here for observability (good to show during the demo)
        return {
            "response": chat_completion.choices[0].message.content,
            "metrics": {
                "tokens_used": chat_completion.usage.total_tokens,
                "model": "llama-3.1-8b-instant",
                "retrieved_chunks": len(results["documents"][0]),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/generate/quiz/")
async def generate_quiz(filename: str = Form(...)):
    """
    Generates a structured JSON quiz.
    The response_format={"type": "json_object"} flag guarantees the frontend can easily map over the data.
    """
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/generate/flashcards/")
async def generate_flashcards(filename: str = Form(...)):
    """
    Generates JSON flashcards for studying.
    """
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



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
    # avoid path traversal
    artifact_name = Path(artifact_name).name
    path = ARTIFACTS_DIR / artifact_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)



@router.post("/generate/code-review/")
async def generate_code_review(filename: str = Form(...)):
    """
    Generates a structured JSON code review.
    Note: This is designed to work best on ingested .py or .js files, not random PDFs.
    """
    try:
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


        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,  # Keep it ultra-low so the code review is strictly analytical
            response_format={"type": "json_object"},
        )


        metrics_counters["total_requests"] += 1
        metrics_counters["total_tokens_used"] += chat_completion.usage.total_tokens


        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))