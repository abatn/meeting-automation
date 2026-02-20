from fastapi import FastAPI, UploadFile, File
import torch
from transformers import pipeline
import os

app = FastAPI(title="Whisper Transcription Service")

# Load model (Mock for setup, would use real Whisper in production)
# device = "cuda:0" if torch.cuda.is_available() else "cpu"
# pipe = pipeline("automatic-speech-recognition", model="openai/whisper-small", device=device)

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # In production:
    # audio = await file.read()
    # result = pipe(audio)
    # return {"text": result["text"]}
    
    return {
        "text": "Ceci est une transcription de test. La réunion a porté sur le projet de transformation digitale. Action: Karim doit finaliser le rapport d'ici vendredi.",
        "language": "fr",
        "segments": []
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "model": "whisper-small"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)