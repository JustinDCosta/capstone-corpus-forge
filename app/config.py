import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "CRITICAL: GROQ_API_KEY is missing from the .env file. Server cannot start."
    )

groq_client = Groq(api_key=GROQ_API_KEY)

# File upload limits
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB — prevents DoS via large file uploads