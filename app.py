import os
import uvicorn
import subprocess
from pathlib import Path
# Hugging Face Spaces Gradio SDK runs on port 7860 by default
PORT = int(os.environ.get("PORT", 7860))
# Pre-ingest demo documents on first boot if the database doesn't exist
if not Path(".data").exists() and Path("sample_docs").exists():
    print("Initializing database with sample documents...")
    
    # Provide a dummy API key just to satisfy initialization checks during ingestion
    original_groq = os.environ.get("GROQ_API_KEY")
    if not original_groq:
        os.environ["GROQ_API_KEY"] = "dummy_key"
        
    subprocess.run(["python", "-m", "backend.cli", "ingest", "sample_docs/"], check=False)
    
    # Restore original environment
    if not original_groq:
        del os.environ["GROQ_API_KEY"]
# Import the FastAPI app (which already contains the logic to serve frontend/dist)
from backend.main import app
if __name__ == "__main__":
    print(f"Starting Research Agent on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)