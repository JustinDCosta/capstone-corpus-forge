import fitz  # PyMuPDF
from fastapi import HTTPException
from .db import collection


def extract_text_from_file(file_path: str, filename: str) -> str:
    """
    Handles raw text extraction. Fails gracefully if the file is corrupted.
    """
    ext = filename.split(".")[-1].lower()
    text = ""

    if ext in ["txt", "md", "py", "js"]:
        # Plain text formats can be read directly with UTF-8.
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to read text file: {str(e)}"
            )

    elif ext == "pdf":
        # PDFs need a parser that can extract page text.
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text("text")
                if page_text:
                    text += page_text + "\n"
            doc.close()

            # Catch PDFs that are just scanned images with no text layer.
            if not text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="PDF is empty or contains only unreadable images. Needs OCR.",
                )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to process PDF: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please stick to txt, md, py, js, or pdf.",
        )

    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Splits massive documents into smaller pieces.
    The overlap is crucial so we don't cut a sentence or concept in half right where the AI needs it.
    """
    chunks = []
    start = 0
    while start < len(text):
        # We take [start:end] where end = start + chunk_size.
        # Then we move start forward by (chunk_size - overlap), so each chunk
        # shares some text with the next one. This preserves context across boundaries.
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
    if not doc_data["documents"]:
        raise HTTPException(
            status_code=404, detail=f"No data found in DB for {filename}"
        )

    # Combine all chunks into one string for generation endpoints.
    # We hard-cap at ~24,000 characters to stay under the model context limit,
    # leaving room for the system prompt and the generated output.
    full_text = "\n\n".join(doc_data["documents"])
    return full_text[:24000]
