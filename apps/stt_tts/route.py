import os
import base64
from io import BytesIO
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from elevenlabs import ElevenLabs

load_dotenv()

voice_router = APIRouter()

ELEVEN_API_KEY = os.getenv("ELEVEN_LABS")
if not ELEVEN_API_KEY:
    raise RuntimeError("ELEVEN_LABS API key not found in environment variables")

client = ElevenLabs(api_key=ELEVEN_API_KEY)


VOICE_ID = os.getenv("VOICE_ID")
TTS_MODEL = "eleven_flash_v2"
STT_MODEL = "scribe_v1"

@voice_router.post("/stt")
async def stt_route(file: UploadFile = File(...)):
    """
    Upload an audio file → returns recognized text using ElevenLabs STT.
    """
    if not file.content_type.startswith("audio/") and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be audio/video format")
    try:
        audio_bytes = await file.read()
        if len(audio_bytes) < 1000:
            raise HTTPException(status_code=400, detail="Audio too short")
        audio_io = BytesIO(audio_bytes)
        transcript = client.speech_to_text.convert(
            file=audio_io,
            model_id=STT_MODEL
        )
        return {
            "success": True,
            "text": transcript.text
        }
    except Exception as e:
        print(f"❌ STT Error: {e}")
        raise HTTPException(status_code=500, detail=f"STT failed: {str(e)}")


@voice_router.post("/stt-base64")
async def stt_base64_route(audio_base64: str = Form(...)):
    """
    Convert base64-encoded audio → text.
    """
    try:
        if not audio_base64.strip():
            raise HTTPException(status_code=400, detail="Audio data required")
        audio_bytes = base64.b64decode(audio_base64)
        if len(audio_bytes) < 1000:
            raise HTTPException(status_code=400, detail="Audio too short")
        audio_io = BytesIO(audio_bytes)
        transcript = client.speech_to_text.convert(
            file=audio_io,
            model_id=STT_MODEL
        )
        return {
            "success": True,
            "text": transcript.text
        }
    except Exception as e:
        print(f"❌ STT-Base64 Error: {e}")
        raise HTTPException(status_code=500, detail=f"STT failed: {str(e)}")


@voice_router.post("/tts")
async def tts_route(text: str = Form(...)):
    """
    Convert text → base64-encoded MP3 using ElevenLabs TTS.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_data = client.text_to_speech.convert(
            voice_id=VOICE_ID,
            model_id=TTS_MODEL,
            text=text,
            voice_settings={
                "stability": 0.35,
                "similarity_boost": 0.8,
                "style": 0.7,
                "use_speaker_boost": True
            }
        )

        if hasattr(audio_data, "__iter__") and not isinstance(audio_data, bytes):
            audio_bytes = b"".join(audio_data)
        else:
            audio_bytes = audio_data

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {"success": True, "audio": audio_b64}

    except Exception as e:
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@voice_router.post("/tts-stream")
async def tts_stream_route(text: str = Form(...)):
    """
    Convert text → stream MP3 directly to the browser (for real-time playback).
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_data = client.text_to_speech.convert(
            voice_id=VOICE_ID,
            model_id=TTS_MODEL,
            text=text
        )
        audio_bytes = b"".join(audio_data) if hasattr(audio_data, "__iter__") and not isinstance(audio_data, bytes) else audio_data
        return StreamingResponse(iter([audio_bytes]), media_type="audio/mpeg")

    except Exception as e:
        print(f"Stream Error: {e}")
        raise HTTPException(status_code=500, detail=f"TTS stream failed: {str(e)}")
