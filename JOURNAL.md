# This Journal gets updated automatically by the Journal Logger Agent

### **New Interaction**
- **Hook Version**: 1.02
- **Date**: 18-05-2026 01:38
- **Prompt**: I am building a FastAPI backend in Python. Create a basic main.py file with CORS middleware enabled and a simple /ping health-check endpoint. I need the code to start the Uvicorn server locally. Do not add any database or AI logic yet.
### **New Interaction**
- **Agent Version**: 2.3
- **Date**: 18-05-2026 01:40
- **User**: justin.d-costa@epita.fr
- **Prompt**: I am building a FastAPI backend in Python. Create a basic main.py file with CORS middleware enabled and a simple /ping health-check endpoint. I need the code to start the Uvicorn server locally. Do not add any database or AI logic yet.
- **CoPilot Mode**: Ask
- **CoPilot Model**: GPT-5.2-Codex
- **Socratic Mode**: ON
- **Changes Made**: No changes.
- **Context and Reasons for Changes**: Asked for clarification on file location, CORS origins, and local run style.

### **New Interaction**
- **Hook Version**: 1.02
- **Date**: 18-05-2026 01:41
- **Prompt**: 1. Put main.py in the repo root. 2. Allow all CORS origins with * for now since we are in local development. 3. Use the if __name__ == "__main__": uvicorn.run(...) method at the bottom of the file so I can just run it with python main.py.
### **New Interaction**
- **Agent Version**: 2.3
- **Date**: 18-05-2026 01:42
- **User**: justin.d-costa@epita.fr
- **Prompt**: 1. Put main.py in the repo root.
2. Allow all CORS origins with * for now since we are in local development.
3. Use the if __name__ == "__main__": uvicorn.run(...) method at the bottom of the file so I can just run it with python main.py.
- **CoPilot Mode**: Edit
- **CoPilot Model**: GPT-5.2-Codex
- **Socratic Mode**: ON
- **Changes Made**: Created main.py with FastAPI app, CORS middleware, /ping endpoint, and uvicorn run entry point.
- **Context and Reasons for Changes**: Implemented requested root-level FastAPI entrypoint with permissive CORS and local dev startup.

### **New Interaction**
- **Hook Version**: 1.02
- **Date**: 18-05-2026 09:29
- **Prompt**: add the requirements to txt accordingly(check main.py)
