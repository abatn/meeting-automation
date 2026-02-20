from fastapi import FastAPI, Body
from typing import List, Optional
from pydantic import BaseModel
import os

app = FastAPI(title="Mistral NLP Service")

class AnalysisRequest(BaseModel):
    text: str
    task: str  # e.g., "extract_actions", "summarize", "validate_pv"
    context: Optional[dict] = None

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    # In production, this would call a local Mistral 7B model or an API
    if request.task == "extract_actions":
        return {
            "actions": [
                {
                    "description": "Finaliser le rapport de transformation digitale",
                    "assignee_name": "Karim",
                    "assignee_phone": "+21699000000",
                    "due_date": "2026-02-27"
                }
            ],
            "summary": "La réunion a porté sur la transformation digitale."
        }
    
    return {
        "result": "Analysis completed",
        "task": request.task
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "model": "mistral-7b-arabic-mock"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)