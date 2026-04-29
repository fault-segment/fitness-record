import io
import os
import ssl
import tempfile

import whisper
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api", tags=["speech"])

_model: "whisper.Whisper | None" = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        # 绕过 SSL 证书问题（macOS Python 常见）
        ssl._create_default_https_context = ssl._create_unverified_context
        model_size = os.getenv("WHISPER_MODEL", "base")
        _model = whisper.load_model(model_size)
    return _model


@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """语音转文字 — Whisper（本地）"""
    contents = await audio.read()

    # Whisper 直接读 bytes 不稳定，写临时文件
    suffix = os.path.splitext(audio.filename or "audio.mp3")[1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(contents)
        tmp_path = f.name

    try:
        model = _get_model()
        result = model.transcribe(tmp_path, language="zh", fp16=False)
        text = result["text"].strip()
        return {"text": text}
    except Exception as e:
        return {"text": "", "error": f"识别失败: {str(e)}"}
    finally:
        os.unlink(tmp_path)
