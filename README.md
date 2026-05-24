# Corpus Forge

Corpus Forge is a local RAG (Retrieval-Augmented Generation) application that lets you upload documents and then ask questions about them using AI. Instead of the AI making things up, it actually reads your files first and bases its answers on what is in them.

Built as a capstone project at EPITA by Justin D'Costa, Krishna Bansal, and Piotr Moczulski.

---

## What Does It Do?

You upload files (PDFs, text files, markdown, Python scripts, or JavaScript files) and the app breaks them into smaller pieces, stores them in a local vector database, and then uses an LLM to answer questions based on that content.

The main features are:

- **Chat** -- Ask questions about your uploaded documents and get answers that are grounded in the actual text.
- **Quiz Generation** -- Automatically create a 5-question multiple choice quiz from any uploaded document.
- **Flashcard Generation** -- Pull out the key concepts from a document and turn them into study flashcards.
- **Code Review** -- Upload a `.py` or `.js` file and get a structured review covering bugs, optimizations, and security concerns.
- **Document Management** -- Upload, list, and delete documents through the UI.
- **Metrics** -- Track how many requests have been made and how many tokens have been used.

---

## How It Works (The Short Version)

1. You upload a file through the Streamlit frontend.
2. The backend extracts the text (using PyMuPDF for PDFs, or just reading the file for everything else).
3. The text gets split into overlapping chunks of about 1000 characters each.
4. Each chunk gets turned into a vector embedding using `all-MiniLM-L6-v2` and stored in ChromaDB.
5. When you ask a question, ChromaDB finds the 3 most relevant chunks.
6. Those chunks get sent to the Groq API (Llama 3.1 8B) along with your question, and the model generates an answer based only on that context.

---

## Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Backend     | FastAPI, Uvicorn                    |
| Frontend    | Streamlit                           |
| Vector DB   | ChromaDB (local, persistent)        |
| Embeddings  | Sentence Transformers (all-MiniLM-L6-v2) |
| LLM         | Groq API with Llama 3.1 8B Instant |
| PDF Parsing | PyMuPDF (fitz)                      |

---

## Project Structure

```
capstone-corpus-forge-main/
├── main.py                 # Entry point, starts the FastAPI server
├── start.py                # Starts backend, waits for readiness, then starts frontend
├── frontend.py             # Streamlit frontend
├── requirements.txt        # Python dependencies
├── .env                    # API keys and local config (not in the repo)
├── app/
│   ├── __init__.py         # Creates the FastAPI app and sets up CORS
│   ├── config.py           # Loads environment variables and sets up the Groq client
│   ├── db.py               # Sets up ChromaDB and the embedding function
│   ├── routes.py           # All the API endpoints
│   └── utils.py            # Text extraction, chunking, and helper functions
├── documentation/
│   └── REPORT.md           # Project report template
├── project_info/           # Course brief and executive summary PDFs
├── JOURNAL.md              # Auto-generated log of development interactions
└── prompts_history.md      # History of prompts used during development
```

---

## Prerequisites

- Python 3.12
- A Groq API key (you can get one for free at [console.groq.com](https://console.groq.com))

---

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/capstone-corpus-forge.git
   cd capstone-corpus-forge
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   ```

   Activate it:

   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** in the project root:

   ```
   GROQ_API_KEY=your_key_here
   
   # Optional: require an API key on every backend request
   CORPUS_FORGE_API_KEY=your_optional_key_here
    
   # Optional: restrict browser origins for CORS (comma-separated)
   ALLOWED_ORIGINS=http://localhost:8501,http://127.0.0.1:8501
   ```

---

## Running the App

**Option A -- One command (recommended):**

```bash
python start.py
```

This starts the backend, waits for `http://127.0.0.1:8000/ping` to return 200, then starts the Streamlit frontend. Press `Ctrl+C` to stop both.

**Option B -- Two terminals (manual):**

**Terminal 1 -- Start the backend:**

```bash
python main.py
```

This starts the FastAPI server on `http://127.0.0.1:8000`. You can check it is running by visiting `http://127.0.0.1:8000/ping` in your browser.

**Terminal 2 -- Start the frontend:**

```bash
streamlit run frontend.py
```

This opens the Streamlit UI in your browser (usually at `http://localhost:8501`).

---

## API Endpoints

| Method | Endpoint                      | What It Does                              |
|--------|-------------------------------|-------------------------------------------|
| GET    | `/ping`                       | Health check                              |
| GET    | `/metrics/`                   | Returns total requests and tokens used    |
| GET    | `/documents/`                 | Lists all uploaded documents              |
| POST   | `/upload/`                    | Upload a file (form field: `file`)        |
| POST   | `/chat/`                      | Ask a question (fields: `query`, `audience_level`, `tone`) |
| POST   | `/generate/quiz/`             | Generate a quiz (field: `filename`)       |
| POST   | `/generate/flashcards/`       | Generate flashcards (field: `filename`)   |
| POST   | `/generate/code-review/`      | Generate a code review (field: `filename`)|
| DELETE | `/documents/{filename}`       | Delete a document and all its chunks      |

If `CORPUS_FORGE_API_KEY` is set, include `X-API-Key: <your_key>` on every request.

---

## Supported File Types

- `.txt` -- Plain text
- `.md` -- Markdown
- `.pdf` -- PDF documents (must contain actual text, not scanned images)
- `.py` -- Python source code
- `.js` -- JavaScript source code

There is a 10 MB file size limit.
