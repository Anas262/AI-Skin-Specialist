import base64
import io
import os
import re
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import Groq
from PIL import Image

# Load environment variables if available locally
load_dotenv()

app = FastAPI(
    title="AI Skin Specialist API",
    description="Serverless API for AI Skin Specialist consultation powered by Groq and Deepgram",
    version="1.0.0",
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clean_doctor_text(text: str) -> str:
    """Strip markdown formatting and special characters so TTS audio sounds natural."""
    if not text:
        return ""
    # Remove asterisks, hashtags, underscores, backticks, emojis
    cleaned = re.sub(r"[\*#_`~]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def encode_image(image_bytes: bytes) -> str:
    """Resize image and encode to base64 JPEG."""
    image = Image.open(io.BytesIO(image_bytes))
    image.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@app.get("/api/health")
@app.get("/health")
@app.get("/api/index.py")
@app.get("/index.py")
@app.get("/api")
async def health_check():
    groq_configured = bool(os.environ.get("GROQ_API_KEY"))
    deepgram_configured = bool(os.environ.get("DEEPGRAM_API_KEY"))
    return {
        "status": "healthy",
        "app": "AI Skin Specialist",
        "services": {
            "groq": "configured" if groq_configured else "missing_key",
            "deepgram": "configured" if deepgram_configured else "missing_key",
        },
    }


@app.post("/api/consult")
@app.post("/consult")
@app.post("/api/index.py")
@app.post("/index.py")
async def consult(
    image: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
):
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not configured on the server. Please set it in Vercel environment variables.",
        )

    deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not deepgram_api_key:
        raise HTTPException(
            status_code=500,
            detail="DEEPGRAM_API_KEY is not configured on the server. Please set it in Vercel environment variables.",
        )

    # 1. Process Voice / Text Input
    transcript = ""
    client = Groq(api_key=groq_api_key)

    if audio and audio.filename:
        try:
            audio_bytes = await audio.read()
            if len(audio_bytes) > 0:
                audio_filename = audio.filename or "recording.webm"
                transcription = client.audio.transcriptions.create(
                    file=(audio_filename, audio_bytes),
                    model=os.environ.get("WHISPER_MODEL", "whisper-large-v3"),
                )
                transcript = transcription.text.strip()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error transcribing audio: {str(e)}",
            )

    if text and text.strip():
        if transcript:
            transcript = f"{text.strip()} (Voice note: {transcript})"
        else:
            transcript = text.strip()

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Please provide a voice recording or type your skin concern description.",
        )

    # 2. Process Image Input
    if not image or not image.filename:
        raise HTTPException(
            status_code=400,
            detail="Visual inspection requires a skin image or video frame. Please upload an image.",
        )

    try:
        image_bytes = await image.read()
        image_data = encode_image(image_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process the uploaded image: {str(e)}",
        )

    # 3. Call Groq Vision Model
    try:
        prompt = (
            "You are a confident, natural doctor specializing in skin care. Speak with the reassurance, clarity, and authority of a real doctor. "
            "Limit your entire response to two or three sentences maximum. "
            "Do not use any special characters, symbols, asterisks, bullet points, or markdown formatting in your response because it will be converted directly to spoken audio.\n\n"
            f"Patient description: {transcript}"
        )

        model_name = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")

        response = client.chat.completions.create(
            model=model_name,
            max_completion_tokens=1000,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful skin care medical specialist. Give compassionate, general skin care guidance, not a definitive diagnosis. Never use markdown, bullet points, or emojis.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                            },
                        },
                    ],
                },
            ],
        )

        raw_guidance = response.choices[0].message.content or ""
        doctor_guidance = clean_doctor_text(raw_guidance)
        if not doctor_guidance:
            doctor_guidance = "I have examined your visual presentation. Please keep the area clean and moisturized, and monitor for changes while following up with a licensed clinician."
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing with AI vision model: {str(e)}",
        )

    # 4. Generate Doctor Voice Audio via Deepgram
    audio_base64 = None
    try:
        from deepgram import DeepgramClient

        deepgram = DeepgramClient(api_key=deepgram_api_key)
        audio_stream = deepgram.speak.v1.audio.generate(
            text=doctor_guidance,
            model=os.environ.get("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en"),
            encoding="mp3",
        )

        tts_buffer = io.BytesIO()
        for chunk in audio_stream:
            tts_buffer.write(chunk)

        audio_bytes_data = tts_buffer.getvalue()
        if audio_bytes_data:
            audio_base64 = f"data:audio/mp3;base64,{base64.b64encode(audio_bytes_data).decode('utf-8')}"
    except Exception as e:
        # If Deepgram fails, we still return the guidance text with an error note
        print(f"Deepgram TTS error: {e}")

    return JSONResponse(
        content={
            "success": True,
            "transcript": transcript,
            "guidance": doctor_guidance,
            "audio": audio_base64,
        }
    )


# Enable local preview when running `uvicorn api.index:app`
if not os.environ.get("VERCEL"):
    BASE_PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    PUBLIC_DIR = os.path.join(BASE_PROJECT_DIR, "public")
    if os.path.isdir(PUBLIC_DIR):
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")
