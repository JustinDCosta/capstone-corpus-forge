from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Corpus Forge API")

# Allow the frontend (Streamlit, React, etc.) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Fine for local dev, restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routes (uses APIRouter to avoid circular imports)
from .routes import router

app.include_router(router)
