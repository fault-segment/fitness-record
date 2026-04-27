from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """语音转文字 — 占位，后续接入腾讯云 ASR / 讯飞 / Whisper"""
    # TODO: 读取 audio.file 内容，调用 ASR 服务
    content_type = audio.content_type or "unknown"
    return {"text": f"[ASR占位] 收到音频: {audio.filename} ({content_type})"}
