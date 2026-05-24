import uvicorn
from app import app

if __name__ == "__main__":
    # Start the FastAPI app with Uvicorn.
    # reload=True is a developer convenience: the server restarts when files change.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
