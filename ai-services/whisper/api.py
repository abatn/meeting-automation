from fastapi import FastAPI, UploadFile, File
import torch
import torchaudio
from transformers import WhisperForConditionalGeneration, WhisperProcessor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Load model and processor
try:
    processor = WhisperProcessor.from_pretrained("openai/whisper-large-v2")
    model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-large-v2")
    model.config.forced_decoder_ids = None
    logger.info("Whisper model loaded successfully.")
except Exception as e:
    logger.error(f"Error loading Whisper model: {e}")
    # Exit if model fails to load
    exit()

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribes an audio file using the Whisper ASR model.
    """
    try:
        # Read audio file
        audio_bytes = await file.read()
        
        # Load audio
        waveform, sample_rate = torchaudio.load(audio_bytes, format=file.content_type.split('/')[-1])
        
        # Resample if necessary
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)

        # Process audio and transcribe
        input_features = processor(waveform.squeeze().numpy(), sampling_rate=16000, return_tensors="pt").input_features
        predicted_ids = model.generate(input_features)
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)
        
        logger.info("Transcription successful.")
        return {"transcription": transcription[0]}

    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return {"error": "Failed to transcribe audio."}, 500

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)