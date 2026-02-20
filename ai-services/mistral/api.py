from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Load model and tokenizer
try:
    model_name = "mistralai/Mistral-7B-v0.1"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    logger.info("Mistral model loaded successfully.")
except Exception as e:
    logger.error(f"Error loading Mistral model: {e}")
    # Exit if model fails to load
    exit()

class Prompt(BaseModel):
    text: str
    max_length: int = 200

@app.post("/generate")
async def generate_text(prompt: Prompt):
    """
    Generates text from a prompt using the Mistral model.
    """
    try:
        inputs = tokenizer(prompt.text, return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=prompt.max_length)
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        logger.info("Text generation successful.")
        return {"generated_text": generated_text}

    except Exception as e:
        logger.error(f"Text generation failed: {e}", exc_info=True)
        return {"error": "Failed to generate text."}, 500

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)