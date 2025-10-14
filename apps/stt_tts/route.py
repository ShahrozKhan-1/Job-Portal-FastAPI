from fastapi import APIRouter, HTTPException, File, UploadFile
import io
from faster_whisper import WhisperModel
import asyncio



voice_router = APIRouter()
model = WhisperModel("small")  


@voice_router.post("/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        audio_bytes = await file.read()
        audio_file = io.BytesIO(audio_bytes) 
        segments, info = await asyncio.to_thread(model.transcribe, audio_file, language="en")
        text = " ".join([seg.text.strip() for seg in segments])
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT processing failed: {str(e)}")
