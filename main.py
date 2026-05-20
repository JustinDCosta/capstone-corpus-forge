import uvicorn
from app import app

if __name__ == "__main__":
    # reload=True ensures the server auto-restarts if we modify this file during local dev.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
