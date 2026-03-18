import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorClient
from openai import OpenAI, APIConnectionError, APIStatusError
from pymongo.errors import PyMongoError

WHISPER_BASE_URL = os.getenv("WHISPER_BASE_URL", "http://localhost:11434/v1")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo-quantized")
WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "ollama")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

client = OpenAI(base_url=WHISPER_BASE_URL, api_key=WHISPER_API_KEY)
db = AsyncIOMotorClient(MONGO_URI)["atc"]

app = FastAPI(title="Whisper Transcription API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(None, description="ISO-639-1 language code (e.g. 'en')"),
    prompt: str = Form(None, description="Optional context prompt"),
    shift_id: Optional[str] = Form(None),
    controller_id: Optional[str] = Form(None),
    facility: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    start_time: Optional[str] = Form(None),
    end_time: Optional[str] = Form(None),
    position: Optional[str] = Form(None),
    schedule_type: Optional[str] = Form(None),
    traffic_count_avg: Optional[int] = Form(None),
    original_file: Optional[str] = Form(None),
):
    print(f"Additional metadata: shift_id={shift_id}, controller_id={controller_id}, facility={facility}, status={status}, start_time={start_time}, end_time={end_time}, position={position}, schedule_type={schedule_type}, traffic_count_avg={traffic_count_avg}, original_file={original_file}")   
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    kwargs = {
        "model": WHISPER_MODEL,
        "file": (file.filename or "audio", content, file.content_type or "application/octet-stream"),
        "response_format": "json",
        "prompt": "Separate text into segments",
        "timestamp_granularities": "segment",
    }
    if language:
        kwargs["language"] = language
    if prompt:
        kwargs["prompt"] = prompt

    print (f"Sending transcription request to Whisper model '{WHISPER_MODEL}' with file '{file.filename}'...")
    try:
        result = client.audio.transcriptions.create(**kwargs)
        
    except APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
        
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Whisper endpoint: {e}")

    doc = {
        "shift_id": shift_id,
        "controller_id": controller_id,
        "facility": facility,
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
        "position": position,
        "schedule_type": schedule_type,
        "traffic_count_avg": traffic_count_avg,
        "original_file": original_file,
        "model": WHISPER_MODEL,
        "language": getattr(result, "language", None),
        "transcription": result.text,
        "segments": [],
        "analysis": "",
        "created_at": datetime.now(timezone.utc),
    }
    print(doc)
    try:
        print("Saving transcription result to MongoDB...")
        insert_result = await db["shift"].insert_one(doc)
        print( f"Document inserted with ID: {insert_result.inserted_id}")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save shift: {e}")
    return {**doc, "_id": str(insert_result.inserted_id), "created_at": doc["created_at"].isoformat()}

@app.get("/shift/{shift_id}")
async def get_shift(shift_id: str):
    try:
        doc = await db["shift"].find_one({"shift_id": shift_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Shift not found")
        doc["_id"] = str(doc["_id"])
        doc["created_at"] = doc["created_at"].isoformat()
        return doc
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve Shift: {e}")       
    

@app.delete("/shift/{shift_id}")
async def delete_shift(shift_id: str):
    try:
        result = await db["shift"].delete_one({"shift_id": shift_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Shift not found")
        return {"detail": "Shift deleted"}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete shift: {e}") 
    