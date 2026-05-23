# Corpus Forge -- Technical Report

## Team Members

| Name              | Email                          | GitHub             |
|-------------------|--------------------------------|--------------------|
| Justin D'Costa    | justin.d-costa@epita.fr        | JustinDCosta       |
| Krishna Bansal    | krishna.bansal@epita.fr        | Krishnabansal2006  |
| Piotr Moczulski   | piotr.moczulski@epita.fr       | POLSKAGUROM727     |

---

## Initial Architecture

The original plan was to build a local RAG (Retrieval-Augmented Generation) pipeline. The idea is simple: let users upload documents, break those documents into smaller pieces, store them in a way that makes them searchable by meaning, and then use an LLM to answer questions based on the content of those documents.

The first version was a single `main.py` file that handled everything -- setting up the server, connecting to the database, extracting text from files, chunking, embedding, and all the API routes. It worked, but it was messy and hard to navigate.

### Initial assumptions

- The app would only run locally on one machine, not on the internet. This meant we could be more relaxed about things like CORS and authentication.
- Users would upload relatively small files (under 10 MB). We were not trying to handle textbooks with thousands of pages.
- ChromaDB's local persistent storage would be enough. We did not need a separate database server.
- The Groq API with Llama 3.1 8B would be fast enough and good enough for generating answers, quizzes, flashcards, and code reviews.
- The frontend did not need to be fancy -- Streamlit was picked because it lets you build a working UI in Python without writing HTML or JavaScript.

### Technical choices

- **FastAPI** for the backend because it is fast, has built-in request validation, and supports async endpoints out of the box.
- **ChromaDB** for vector storage because it runs locally without needing a server, and it has a simple Python API.
- **Sentence Transformers (all-MiniLM-L6-v2)** for embeddings because it is a small model (about 80 MB) that runs on CPU and still produces decent embeddings.
- **Groq API** instead of running a local LLM because it gives us access to Llama 3.1 8B with very low latency and we do not need a GPU.
- **PyMuPDF (fitz)** for PDF text extraction because it is faster and more reliable than most alternatives like pdfplumber or PyPDF2.
- **Streamlit** for the frontend because it is the fastest way to get a working UI without learning a frontend framework.

---

## Engineering Decisions

### 1. Single file vs. package structure

**Problem:** The original `main.py` was around 300 lines and handled config, database setup, utility functions, and all the route handlers in one file. It was hard to find anything.

**Alternatives considered:**
- Keep everything in one file (simpler, but ugly).
- Split into a proper Python package with separate modules.

**Decision:** We refactored into an `app/` package with four modules: `config.py` (environment variables and API client), `db.py` (ChromaDB setup), `utils.py` (text extraction and chunking), and `routes.py` (all the API endpoints). `main.py` became a thin entry point that just imports the app and starts uvicorn. This made the code much easier to work with because you could open just the file you needed.

### 2. Chunking strategy

**Problem:** LLMs have a limited context window. You cannot just dump an entire 50-page PDF into the prompt.

**Alternatives considered:**
- Chunk by sentence (too small, loses context).
- Chunk by paragraph (inconsistent sizes depending on the document).
- Chunk by fixed character count with overlap.

**Decision:** We went with fixed-size chunks of 1000 characters with a 200-character overlap. The overlap means that if an important sentence gets cut in half at the boundary, the next chunk will still have the beginning of that sentence. It is not perfect, but it is simple and works well enough for our use case.

### 3. Embedding model

**Problem:** We needed a way to turn text chunks into vectors so we could search by meaning.

**Alternatives considered:**
- OpenAI embeddings (costs money per request).
- A larger Sentence Transformers model (better quality but slower).
- `all-MiniLM-L6-v2` (small, fast, free, runs on CPU).

**Decision:** `all-MiniLM-L6-v2`. It is one of the most commonly used embedding models for a reason -- it is small, it runs without a GPU, and the embedding quality is good enough for a project like this. The tradeoff is that it is not as accurate as larger models, but for a capstone demo it does the job.

### 4. Using Groq instead of a local LLM

**Problem:** We needed an LLM to generate answers, quizzes, flashcards, and code reviews. Running one locally would need a good GPU.

**Alternatives considered:**
- Run a local model with Ollama (no API key needed, but slow without a GPU).
- Use OpenAI's API (great quality, but costs money).
- Use Groq's API (free tier, very fast inference, runs Llama 3.1).

**Decision:** Groq. The free tier is generous enough for a capstone project, the inference speed is faster than most alternatives, and Llama 3.1 8B handles structured JSON output well with the `response_format={"type": "json_object"}` flag.

### 5. Temp file handling for uploads

**Problem:** PyMuPDF needs a file path on disk to open PDFs. FastAPI gives you the file content in memory. So we need to save it to disk temporarily.

**Alternatives considered:**
- Save uploaded files permanently in a folder (wastes disk space, security risk).
- Use `tempfile.NamedTemporaryFile` with `delete=True` (file gets deleted when closed, but might not get deleted if something crashes before the close).
- Use `tempfile.NamedTemporaryFile` with `delete=False` and manually delete in a `finally` block.

**Decision:** We went with option 3. The `finally` block runs no matter what -- even if the text extraction crashes -- so the temp file always gets cleaned up. This prevents disk bloat during long demo sessions.

### 6. Anti-duplicate logic on upload

**Problem:** If you upload the same file twice, you end up with duplicate chunks in the database, and the AI starts returning repeated information.

**Decision:** Before adding new chunks, the upload endpoint checks if any chunks with the same filename already exist in ChromaDB. If they do, it deletes them first, then adds the new ones. This means re-uploading a file is basically an "update" operation.

### 7. Context cap for generation endpoints

**Problem:** The quiz, flashcard, and code review endpoints pull all chunks for a file and concatenate them. If the file is large, this string could exceed Llama 3.1's context window (8192 tokens).

**Decision:** We hard-cap the combined text at 24,000 characters (roughly 6,000 tokens) to leave room for the system prompt and the generated output. This is a rough heuristic, not a precise token count, but it prevents the model from getting confused or truncating its response.

### 8. Streamlit over React or a custom frontend

**Problem:** We needed a frontend but did not want to spend weeks building one.

**Alternatives considered:**
- React (powerful but overkill for this, and would need to learn JSX).
- Plain HTML/JS (simple but tedious for forms and state management).
- Streamlit (Python-only, fast to build, handles UI state for you).

**Decision:** Streamlit. The entire frontend is one Python file (330 lines). It is not the most customizable framework, but for a demo-oriented capstone project, being able to build the whole UI in an afternoon is worth the tradeoff.

---

## Division of Work

The project was originally divided by layer:

- **Justin D'Costa** -- Led the backend development. Built the initial `main.py` with all the FastAPI endpoints, the RAG pipeline (upload, chunk, embed, query), and the structured JSON generation endpoints (quiz, flashcards, code review). Also ran the security audit.
- **Krishna Bansal** -- Worked on document processing and testing. Helped with the text extraction logic, chunking parameters, and testing different file types to make sure PDFs, Markdown, and code files all got parsed correctly.
- **Piotr Moczulski** -- Handled the frontend and integration. Built the Streamlit interface, connected it to the backend API, and added the document management sidebar, metrics panel, and all the feature tabs.

### How responsibilities changed over time

As the project progressed, the lines blurred a bit. When the codebase got refactored from a single file into the `app/` package, everyone had to understand the full stack to keep working. The security audit findings were discussed as a team and fixes were applied collaboratively. Toward the end, everyone was debugging and testing end-to-end rather than working in isolated layers.

---

## AI Collaboration

### Tools used

- **GitHub Copilot** (GPT-5 mini and GPT-5.2 Codex) -- Used for code generation in edit mode and for explanations in ask mode.
- **Gemini (via Antigravity)** -- Used for writing documentation and the README.

### How AI was used

AI was used throughout the project, but in a deliberate, incremental way. Rather than asking the AI to "build the whole app," the prompts were broken into small, specific tasks. Looking at the prompt history, you can see the progression:

1. **Security audit first** -- Before writing any new code, the existing backend was submitted for a thorough security review. The AI was asked to act as a security engineer and find vulnerabilities. This was done on May 18th, before any other changes.

2. **Refactoring** -- The AI was asked to restructure the single-file backend into a package, but explicitly told "do not change any logic." This kept the refactor safe.

3. **Concept explanations before code** -- Before building the frontend, the team asked the AI to explain concepts first: "How does Streamlit communicate with a FastAPI backend?" and "What security risks exist when handling file uploads?" Only after understanding the concepts were code changes requested.

4. **Incremental frontend building** -- The frontend was built in six separate prompts, each adding one small piece:
   - First, just the file structure with TODO stubs.
   - Then the sidebar upload and document list.
   - Then the Chat tab.
   - Then Quiz and Flashcards.
   - Then Code Review.
   - Then the delete button and metrics panel.

5. **Security hardening** -- The upload file size limit was added after the AI explained the denial-of-service risk and showed the fix pattern. The temp file cleanup in a `finally` block also came from the security audit.

### How AI influenced decisions

- The package structure (`app/config.py`, `app/db.py`, `app/utils.py`, `app/routes.py`) was suggested by the AI during the refactoring prompt. The team reviewed it and agreed it made sense.
- The `MAX_UPLOAD_BYTES` constant (10 MB limit) was added based on the AI's security audit, which flagged that the upload endpoint had no size limit and was vulnerable to denial-of-service attacks.
- The `try/finally` pattern for temp file cleanup was suggested by the AI during the security review.

### How AI suggestions were evaluated

- Every AI-generated code change was reviewed before being accepted. The journal shows that "CoPilot Mode" was set to either "Ask" (explain but do not change code) or "Edit" (make changes). The team used "Ask" mode first to understand the problem, then switched to "Edit" mode for the actual changes.
- AI outputs were tested by running the backend and frontend locally and manually checking that endpoints still worked after each change.
- The security audit was run as a read-only analysis. The AI was told "do not compliment my code; only look for vulnerabilities." The team then decided which findings to fix and which to leave as known limitations.

---

## Failures and Redesigns

### The monolithic main.py

The biggest early mistake was putting everything in one file. It worked fine when the project had three endpoints, but once it grew to nine endpoints plus helper functions plus config, it became painful to scroll through 300+ lines to find anything. The refactor into the `app/` package fixed this, but it should have been done from the start.

### Journal logging duplication

The journal logger agent had a bug where it would sometimes log the same prompt twice. You can see this in `JOURNAL.md` -- several entries are duplicated. The team noticed this and asked "why are you adding two interactions of one prompt?" but the root cause was in the hook configuration, not the code. It was a minor annoyance rather than a real problem, but it cluttered the development log.

### File path confusion during refactoring

During the refactoring session, the journal and prompt history files got moved from the root directory to a `records/` folder and then back to root. This caused some confusion with the AI logger not knowing where to write. It took a few prompts to sort out ("no, the files are in records now" followed by "ok, it's in root now, do as you always have"). This was a coordination issue, not a code issue.

### CORS left wide open

The CORS middleware is set to `allow_origins=["*"]`, which means any website can make requests to the backend. The security audit flagged this, and the team acknowledged it, but since the app only runs locally it was left as-is with a comment explaining the tradeoff. For a production deployment, this would need to be locked down to specific origins.

### In-memory metrics do not persist

The metrics counter (`total_requests` and `total_tokens_used`) is a plain Python dictionary that lives in memory. Every time the server restarts, the counters reset to zero. A proper solution would be to store them in a database or a file, but for a demo project the in-memory approach was good enough.

### No token counting before sending to the LLM

The 24,000-character hard cap on context is a rough approximation. Characters and tokens are not the same thing (one token is roughly 4 characters for English text, but it varies). There is a risk that some documents still exceed the context window. A better approach would be to use a proper tokenizer to count tokens, but we did not implement this.

---

## "When AI Failed or Was Wrong"

### Double journal entries

As mentioned above, the AI-powered journal logger sometimes recorded the same interaction twice. The team caught this by reading the journal file and noticing duplicate entries. The fix was not in the code itself but in how the hook was configured.

### Overly eager refactoring

When asked to refactor into a package structure, the AI initially tried to write the changes to the wrong directory (it was confused about whether files lived in `records/` or in root). This required a few back-and-forth messages to correct. The lesson here is that the AI does not always know the current state of the filesystem and you need to be explicit about where files are.

### Security suggestions that were not practical

The security audit produced a long list of vulnerabilities and fixes. Some of them were good and got implemented (file size limits, temp file cleanup). Others were technically correct but not practical for a local capstone project -- for example, the suggestion to implement rate limiting, input sanitization for prompt injection, and restricted CORS origins. These were noted as known limitations rather than implemented, because the effort to implement them properly did not match the scope of the project.

---

## Lessons Learned

### Technical growth

- **Understanding RAG from end to end.** Before this project, "RAG" was just a buzzword. After building the whole pipeline -- upload, extract, chunk, embed, store, retrieve, generate -- it became clear how each step works and why each one matters. Chunking strategy, embedding model choice, and context window limits are all things you only really understand once you run into problems with them.
- **FastAPI is great for quick APIs.** The automatic documentation at `/docs`, built-in validation, and async support made it easy to build and test endpoints without much boilerplate.
- **Vector databases are simpler than expected.** ChromaDB's API is straightforward -- `add`, `query`, `get`, `delete`. The hard part is not the database itself, it is choosing the right embedding model and chunk size.
- **Structured JSON output from LLMs.** Using `response_format={"type": "json_object"}` with Groq was a game changer. Without it, the model would sometimes return JSON wrapped in markdown code blocks or add conversational text around it, which broke parsing.

### Workflow improvements

- **Ask first, code second.** The pattern of asking the AI to explain a concept before asking it to write code turned out to be really effective. It meant we understood what the code was doing instead of just copy-pasting it.
- **Small, incremental prompts work better than big ones.** Building the frontend in six small steps (stubs, then sidebar, then one tab at a time) was much more reliable than asking for the whole thing at once. Each step could be tested before moving to the next one.
- **Security audits early, not at the end.** Running the security audit before building the frontend meant the hardening fixes (file size limits, temp cleanup) were already in place when the frontend started uploading files.

### Strengths and limitations of AI-assisted development

**Strengths:**
- AI is very good at boilerplate. Setting up a FastAPI app, connecting to ChromaDB, writing Streamlit forms -- these are all well-documented patterns and the AI generates them accurately.
- AI is useful as a reviewer. The security audit found real issues (no file size limit, temp files not guaranteed to be cleaned up) that might have been missed otherwise.
- AI is good at explaining concepts in plain language, which helped the team get up to speed on topics like vector embeddings and RAG pipelines.

**Limitations:**
- AI does not know the current state of your project unless you tell it. The file path confusion during refactoring happened because the AI assumed files were in one location when they had been moved.
- AI suggestions need to be filtered. Not everything the security audit suggested was worth implementing. Blindly applying every suggestion would have doubled the codebase for marginal benefit.
- AI-generated code still needs to be tested. The code it produced generally worked, but there were small issues (like duplicate journal entries) that only showed up during actual use.
