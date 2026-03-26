import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from openai import OpenAI, APIConnectionError, APIStatusError
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import (
    db,
    whisper_client,
    llama_client,
    WHISPER_MODEL,
    GRANITE_BASE_URL,
    DEFAULT_QUERY_TEMPLATE,
)
from models import AnalysisResponse, TranscriptRequest
from rag import clean_text, run_rag_query

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


@router.post("/transcribe")
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
    print("inside of transcribe endpoint")
    print(
        f"Additional metadata: shift_id={shift_id}, controller_id={controller_id}, "
        f"facility={facility}, status={status}, start_time={start_time}, "
        f"end_time={end_time}, position={position}, schedule_type={schedule_type}, "
        f"traffic_count_avg={traffic_count_avg}, original_file={original_file}"
    )

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

    print(f"Sending transcription request to Whisper model '{WHISPER_MODEL}' with file '{file.filename}'...")
    try:
        result = whisper_client.audio.transcriptions.create(**kwargs)

        granite_client = OpenAI(base_url=GRANITE_BASE_URL, api_key="YOUR_TOKEN")
        clean_result = clean_text(result.text)
        granite_prompt = f"""
        You are an expert in air traffic control (ATC) communications and noisy transcript reconstruction.

        Your task is to transform a messy, error-filled transcript into a clean, readable conversation between a Pilot and an Air Traffic Controller.

        CRITICAL RULES:
        - The input contains transcription errors, repetition, and noise. You MUST clean it aggressively.
        - Remove repeated phrases, duplicate words, and obvious transcription artifacts.
        - Ignore nonsensical fragments (e.g., repeated callsigns, numbers, partial words like \"Flattus 5 Flattus 5 Flattus 5\").
        - Reconstruct broken sentences into clear, natural aviation communication.
        - You MAY fix obvious transcription mistakes using context (e.g., \"Romyocera\" → \"Romeo Sierra\").
        - Split unrelated conversations into separate exchanges if needed, but keep a single continuous output.

        SPEAKER IDENTIFICATION:
        - Controller:
        - Gives instructions (clear to land, hold short, taxi)
        - Asks status or provides assistance
        - Pilot:
        - Reports position, issues, or acknowledges instructions

        FORMATTING RULES:
        - ONLY use:
        Pilot:
        Controller:
        - Alternate speakers naturally based on conversation flow
        - Merge consecutive lines from the same speaker into one clean sentence
        - Keep each line concise and meaningful

        DO NOT:
        - Include repeated spam phrases
        - Include broken or partial words
        - Output raw or uncleaned text
        - Explain anything

        OUTPUT FORMAT (STRICT):
        Pilot: <clean sentence>
        Controller: <clean sentence>

        ---

        Transcript:
        {clean_result}
        """

        response = granite_client.chat.completions.create(
            model="granite32-8b",
            messages=[{"role": "user", "content": granite_prompt}],
            temperature=0.3,
        )
        result.text = response.choices[0].message.content

    except APIStatusError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Whisper endpoint: {e}")

    doc = {
        "shift_id": shift_id,
        "controller_id": controller_id,
        "facility": facility,
        "status": "transcribed",
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
        print(f"Document inserted with ID: {insert_result.inserted_id}")
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"Shift '{shift_id}' already exists")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save shift: {e}")

    return {**doc, "_id": str(insert_result.inserted_id), "created_at": doc["created_at"].isoformat()}


@router.get("/shift/{shift_id}")
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


@router.delete("/shift/{shift_id}")
async def delete_shift(shift_id: str):
    try:
        result = await db["shift"].delete_one({"shift_id": shift_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Shift not found")
        return {"detail": "Shift deleted"}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete shift: {e}")


@router.get("/shifts")
async def get_shifts(
    page: int = 1,
    page_size: int = 10,
    sort_order: str = "desc",
    facility: str = None,
    status: str = None,
):
    skip = (page - 1) * page_size
    filter_dict = {}
    if facility:
        filter_dict["facility"] = facility
    if status:
        filter_dict["status"] = status

    sort_dict = {"created_at": 1 if sort_order == "asc" else -1}

    try:
        cursor = db["shift"].find(filter_dict).sort(list(sort_dict.items())).skip(skip).limit(page_size)
        shifts = await cursor.to_list(length=page_size)
        total_shifts = await db["shift"].count_documents(filter_dict)
        total_pages = (total_shifts + page_size - 1) // page_size

        for shift in shifts:
            shift["_id"] = str(shift["_id"])
            shift["created_at"] = shift["created_at"].isoformat()

        return {
            "shifts": shifts,
            "metadata": {
                "total_shifts": total_shifts,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
            },
        }
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve shifts: {e}")


# ---------------------------------------------------------------------------
# Shift analysis
# ---------------------------------------------------------------------------


@router.post("/analyze_transcript", response_model=AnalysisResponse)
async def analyze_transcript(req: TranscriptRequest, request: Request):
    transcription = req.transcription

    if req.shift_id:
        try:
            doc = await db["shift"].find_one({"shift_id": req.shift_id})
            print(f"Loaded shift document for analysis: {doc}")
        except PyMongoError as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve shift: {e}")
        if not doc:
            raise HTTPException(status_code=404, detail=f"Shift '{req.shift_id}' not found")
        transcription = doc.get("transcription") or transcription

    if not transcription:
        raise HTTPException(status_code=400, detail="Provide either shift_id (to load from DB) or transcription")

    query = req.query or DEFAULT_QUERY_TEMPLATE.format(transcription=transcription)

    model = request.app.state.model
    vector_store_id = request.app.state.vector_store_id

    try:
        analysis = run_rag_query(llama_client, model, vector_store_id, query)
        doc_update = {"analysis": analysis, "status": "analyzed"}
        await db["shift"].update_one({"shift_id": req.shift_id}, {"$set": doc_update})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

    return AnalysisResponse(
        shift_id=req.shift_id,
        vector_store_id=vector_store_id,
        analysis=analysis,
    )
