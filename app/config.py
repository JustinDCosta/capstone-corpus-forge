import os
from dotenv import load_dotenv
from groq import Groq

# Load variables from .env so local dev does not require manual exports.
load_dotenv()

# Required to call Groq's LLM API.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Optional: comma-separated list of allowed browser origins for CORS.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")

if not GROQ_API_KEY:
    raise ValueError(
        "CRITICAL: GROQ_API_KEY is missing from the .env file. Server cannot start."
    )

# A single Groq client reused across requests.
groq_client = Groq(api_key=GROQ_API_KEY)

# File upload limit used by the upload endpoint.
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB