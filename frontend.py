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
            st.sidebar.write(f"- {document_name}")
    else:
        st.sidebar.info("No documents found yet.")


def render_upload_tab() -> None:
    """Render the upload tab scaffold."""
    st.header("Upload")
    st.write("TODO: Build the upload workflow for POST /upload/.")


def render_chat_tab() -> None:
    """Render the RAG chat tab scaffold."""
    st.header("Chat with Corpus")
    st.write("TODO: Build the chat form for POST /chat/.")
    st.write("TODO: Include query, audience_level, and tone inputs.")


def render_quiz_tab() -> None:
    """Render the quiz generation tab scaffold."""
    st.header("Generate Quiz")
    st.write("TODO: Build the quiz generation form for POST /generate/quiz/.")
    st.write("TODO: Add filename selection and quiz display placeholders.")


def render_flashcards_tab() -> None:
    """Render the flashcards generation tab scaffold."""
    st.header("Generate Flashcards")
    st.write("TODO: Build the flashcards form for POST /generate/flashcards/.")
    st.write("TODO: Add filename selection and flashcard display placeholders.")


def render_code_review_tab() -> None:
    """Render the code review tab scaffold."""
    st.header("Generate Code Review")
    st.write("TODO: Build the code review form for POST /generate/code-review/.")
    st.write("TODO: Add filename selection and review display placeholders.")


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
