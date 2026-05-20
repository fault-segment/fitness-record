import io
import os
import ssl
import tempfile

import whisper
from fastapi import APIRouter, UploadFile, File
from loguru import logger

router = APIRouter(prefix="/api", tags=["speech"])

_model: "whisper.Whisper | None" = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        ssl._create_default_https_context = ssl._create_unverified_context
        model_size = os.getenv("WHISPER_MODEL", "base")
        _model = whisper.load_model(model_size)
    return _model


@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """语音转文字 — Whisper（本地）"""
    contents = await audio.read()

    suffix = os.path.splitext(audio.filename or "audio.mp3")[1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(contents)
        tmp_path = f.name

    try:
        model = _get_model()
        result = model.transcribe(tmp_path, language="zh", fp16=False)
        text = result["text"].strip()
        logger.debug("Whisper transcribed: {text}", text=text[:50])
        return {"text": text}
    except Exception:
        logger.exception("Whisper transcription failed for file {name}", name=audio.filename)
        return {"text": "", "error": "识别失败"}
    finally:
        os.unlink(tmp_path)
