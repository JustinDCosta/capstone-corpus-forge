import streamlit as st
import httpx

BACKEND_URL = "http://127.0.0.1:8000"


def fetch_documents() -> list[str]:
    """Fetch the current document list from the FastAPI backend."""
    try:
        response = httpx.get(f"{BACKEND_URL}/documents/", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        documents = payload.get("documents", [])
        return documents if isinstance(documents, list) else []
    except Exception as exc:
        st.sidebar.error(f"Failed to load documents: {exc}")
        return []


def upload_document(uploaded_file) -> None:
    """Upload a file to the FastAPI backend."""
    try:
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        }
        response = httpx.post(f"{BACKEND_URL}/upload/", files=files, timeout=60.0)
        response.raise_for_status()
        payload = response.json()
        st.sidebar.success(payload.get("message", "Upload complete."))
        st.session_state["documents"] = fetch_documents()
    except Exception as exc:
        st.sidebar.error(f"Upload failed: {exc}")


def render_sidebar() -> None:
    """Render the document management sidebar."""
    st.sidebar.title("Document Management")
    st.sidebar.caption(f"Backend: {BACKEND_URL}")

    st.sidebar.subheader("Upload document")
    uploaded_file = st.sidebar.file_uploader(
        "Choose a file",
        type=["txt", "md", "pdf", "py", "js"],
        label_visibility="collapsed",
    )

    if st.sidebar.button("Upload to backend", use_container_width=True):
        if uploaded_file is None:
            st.sidebar.warning("Choose a file first.")
        else:
            upload_document(uploaded_file)

    st.sidebar.divider()
    st.sidebar.subheader("Documents")

    if "documents" not in st.session_state:
        st.session_state["documents"] = fetch_documents()

    if st.sidebar.button("Refresh documents", use_container_width=True):
        st.session_state["documents"] = fetch_documents()

    documents = st.session_state.get("documents", [])
    if documents:
        st.sidebar.selectbox("Available documents", documents, key="selected_document")
        st.sidebar.write("Current index:")
        for document_name in documents:
            cols = st.sidebar.columns([0.78, 0.22])
            cols[0].write(document_name)
            # Unique key per document to avoid collisions
            btn_key = f"delete_{document_name}"
            if cols[1].button("Delete", key=btn_key, use_container_width=True):
                try:
                    resp = httpx.delete(
                        f"{BACKEND_URL}/documents/{document_name}", timeout=30.0
                    )
                    resp.raise_for_status()
                    st.sidebar.success(resp.json().get("message", "Deleted."))
                    # Refresh local document list
                    st.session_state["documents"] = fetch_documents()
                    # Clear selection if it was the deleted file
                    if st.session_state.get("selected_document") == document_name:
                        st.session_state["selected_document"] = None
                except Exception as exc:
                    st.sidebar.error(f"Delete failed: {exc}")
    else:
        st.sidebar.info("No documents found yet.")


def render_upload_tab() -> None:
    """Render the upload tab."""
    st.header("Upload Documents")
    st.info("Use the sidebar on the left to upload and manage documents.")
    st.write("Supported formats: .txt, .md, .pdf, .py, .js")
    st.write("After uploading, select a document from the sidebar to use it in Chat, Quiz, Flashcards, or Code Review.")


def render_chat_tab() -> None:
    """Render the RAG chat tab."""
    st.header("Chat with Corpus")

    with st.form("chat_form"):
        query = st.text_area(
            "Query",
            placeholder="Ask a question about the uploaded corpus...",
            height=160,
        )
        audience_level = st.selectbox(
            "Audience level",
            ["expert", "intermediate", "beginner"],
            index=0,
        )
        tone = st.selectbox(
            "Tone",
            ["professional", "friendly", "concise", "detailed"],
            index=0,
        )
        submitted = st.form_submit_button("Send to backend", use_container_width=True)

    if submitted:
        if not query.strip():
            st.warning("Enter a query first.")
            return

        try:
            response = httpx.post(
                f"{BACKEND_URL}/chat/",
                data={
                    "query": query,
                    "audience_level": audience_level,
                    "tone": tone,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            payload = response.json()

            st.subheader("Response")
            st.write(payload.get("response", "No response returned."))

            metrics = payload.get("metrics", {})
            st.subheader("Token metrics")
            st.json(metrics)
        except Exception as exc:
            st.error(f"Chat request failed: {exc}")


def render_quiz_tab() -> None:
    """Render the quiz generation tab and request quiz JSON from the backend."""
    st.header("Generate Quiz")

    filename = st.session_state.get("selected_document")
    if not filename:
        st.info("Select a document in the sidebar to enable quiz generation.")
        return

    st.write(f"Generating quiz for: **{filename}**")
    if st.button("Generate Quiz", use_container_width=True):
        with st.spinner("Requesting quiz from backend..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/generate/quiz/",
                    data={"filename": filename},
                    timeout=120.0,
                )
                resp.raise_for_status()
                quiz_obj = resp.json()
                st.subheader("Quiz JSON")
                st.json(quiz_obj)
            except Exception as exc:
                st.error(f"Quiz generation failed: {exc}")


def render_flashcards_tab() -> None:
    """Render the flashcards generation tab and request flashcards JSON from the backend."""
    st.header("Generate Flashcards")

    filename = st.session_state.get("selected_document")
    if not filename:
        st.info("Select a document in the sidebar to enable flashcard generation.")
        return

    st.write(f"Generating flashcards for: **{filename}**")
    if st.button("Generate Flashcards", use_container_width=True):
        with st.spinner("Requesting flashcards from backend..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/generate/flashcards/",
                    data={"filename": filename},
                    timeout=120.0,
                )
                resp.raise_for_status()
                cards_obj = resp.json()
                st.subheader("Flashcards JSON")
                st.json(cards_obj)
            except Exception as exc:
                st.error(f"Flashcards generation failed: {exc}")


def render_code_review_tab() -> None:
    """Render the code review tab and request a structured review from the backend.

    Only available for `.py` and `.js` documents.
    """
    st.header("Generate Code Review")

    filename = st.session_state.get("selected_document")
    if not filename:
        st.info("Select a document in the sidebar to enable code review.")
        return

    if not filename.lower().endswith((".py", ".js")):
        st.info("Code review is only available for .py and .js files.")
        return

    st.write(f"Generating code review for: **{filename}**")
    if st.button("Generate Code Review", use_container_width=True):
        with st.spinner("Requesting code review from backend..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/generate/code-review/",
                    data={"filename": filename},
                    timeout=120.0,
                )
                resp.raise_for_status()
                body = resp.json()

                review = body.get("review") or {}

                st.subheader("Summary")
                st.write(review.get("summary", "No summary returned."))

                st.subheader("Bugs")
                bugs = review.get("bugs", [])
                if bugs:
                    for b in bugs:
                        st.write(f"- {b}")
                else:
                    st.write("No bugs identified.")

                st.subheader("Optimizations")
                opts = review.get("optimizations", [])
                if opts:
                    for o in opts:
                        st.write(f"- {o}")
                else:
                    st.write("No optimizations suggested.")

                st.subheader("Security Concerns")
                secs = review.get("security_concerns", [])
                if secs:
                    for s in secs:
                        st.write(f"- {s}")
                else:
                    st.write("No security concerns identified.")

            except Exception as exc:
                st.error(f"Code review request failed: {exc}")


def main() -> None:
    st.set_page_config(page_title="Corpus Forge Frontend", layout="wide")

    st.title("Corpus Forge")
    st.caption("Streamlit frontend scaffold for the FastAPI RAG backend.")

    render_sidebar()

    upload_tab, chat_tab, quiz_tab, flashcards_tab, review_tab = st.tabs(
        ["Upload", "Chat", "Quiz", "Flashcards", "Code Review"]
    )

    with upload_tab:
        render_upload_tab()

    with chat_tab:
        render_chat_tab()

    with quiz_tab:
        render_quiz_tab()

    with flashcards_tab:
        render_flashcards_tab()

    with review_tab:
        render_code_review_tab()


if __name__ == "__main__":
    main()
