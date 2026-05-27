from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import ALLOWED_ORIGINS


def get_allowed_origins() -> list[str]:
    # If ALLOWED_ORIGINS is not set, only allow local Streamlit during dev.
    if not ALLOWED_ORIGINS:
        return ["http://localhost:8501", "http://127.0.0.1:8501"]
    # Comma-separated list in .env, e.g. "http://example.com,http://localhost:8501"
    return [origin.strip() for origin in ALLOWED_ORIGINS.split(",") if origin.strip()]

app = FastAPI(title="Corpus Forge API")

# Allow the frontend (Streamlit, React, etc.) to talk to this backend.
# CORS controls which browser origins can make requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routes (uses APIRouter to avoid circular imports).
from .routes import router

app.include_router(router)
