import os
import re
from unittest import result
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from openai import OpenAI, APIConnectionError, APIStatusError
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, PyMongoError
from llama_stack_client import RAGDocument
from llama_stack_client import LlamaStackClient, Agent, AgentEventLogger

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLAMA_STACK_URL = os.getenv("LLAMA_STACK_URL", "http://localhost:8321")
WHISPER_BASE_URL = os.getenv("WHISPER_BASE_URL", "http://localhost:11434/v1")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo-quantized")
WHISPER_API_KEY = os.getenv("WHISPER_API_KEY", "ollama")
GRANITE_BASE_URL=os.getenv("GRANITE_BASE_URL", "http://localhost:11434/v1")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

FAA_AIM_URLS = [
    ("https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap4_section_2.html", "text/html"),
    ("https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_1.html", "text/html")
]

DEFAULT_QUERY_TEMPLATE = (
    "You are an air traffic control shift supervisor reviewing a controller's transcript. "
    "Analyze the following transcript for procedural compliance, communication quality, "
    "and any deviations from FAA standard phraseology or procedures. "
    "Provide a structured assessment with specific findings.\n\n"
    "Transcript:\n{transcription}"
)

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

llama_client = LlamaStackClient(base_url=LLAMA_STACK_URL)
whisper_client = OpenAI(base_url=WHISPER_BASE_URL, api_key=WHISPER_API_KEY)
db = AsyncIOMotorClient(MONGO_URI)["atc"]


async def lifespan(app: FastAPI):
    await db["shift"].create_index("shift_id", unique=True, sparse=True)
    yield


app = FastAPI(title="ATC API", version="1.0.0", lifespan=lifespan)

# Allow browser clients from any origin. Restrict CORS_ORIGINS to specific
# URLs in production (comma-separated, e.g. "https://atc-web-ui.example.com").
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TranscriptRequest(BaseModel):
    shift_id: Optional[str] = None
    doc: Optional[dict] = None  # Full shift document from DB (if shift_id is provided)
    transcription: Optional[str] = None  # Required if shift_id is not provided
    query: Optional[str] = None  # Override the default analysis query


class AnalysisResponse(BaseModel):
    shift_id: Optional[str]
    vector_store_id: str
    analysis: str

# ---------------------------------------------------------------------------
# RAG helpers
# ---------------------------------------------------------------------------

def clean_text(text):
    # remove repeated words (basic)
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)
    
    # remove weird numeric spam
    text = re.sub(r'(\d+\.){2,}', '', text)
    
    return text


def build_llm_model(client: LlamaStackClient) -> str:
    print("Fetching available models from Llama Stack...")
    models = list(client.models.list())
    print(f"Total models available: {len(models)}")

    llm_models = [m for m in models if m.identifier and not m.identifier.startswith("sentence-transformers")]
    ollama_models = [m for m in llm_models if "granite32" in m.identifier]
    if not llm_models:
        raise HTTPException(status_code=503, detail="No LLM models available on Llama Stack server")
    print(f"Available LLM models: {[m.identifier for m in llm_models]}")
    print(llm_models[1].identifier)

    return llm_models[1].identifier #(ollama_models[0] if ollama_models else llm_models[1]).identifier


def ingest_urls(client: LlamaStackClient, urls: list[str]) -> str:
    """Download FAA AIM pages, upload to Llama Stack, and return a vector store ID."""
    print("Ingesting FAA AIM documents...")
    vector_db_id = f"aim_docs_{uuid.uuid4()}"

    client.vector_dbs.register(
        vector_db_id=vector_db_id,
        embedding_model="all-MiniLM-L6-v2",
        embedding_dimension=int(os.getenv("VDB_EMBEDDING_DIMENSION", 384)),
        provider_id="milvus",
    )
    print(f"Vector database '{vector_db_id}' registered successfully.")
    documents = [
        RAGDocument(
            document_id=f"num-{i}",
            content=url,
            mime_type=url_type,
            metadata={},
        )
        for i, (url, url_type) in enumerate(FAA_AIM_URLS)
    ]
    print(f"Inserting documents into vector database '{vector_db_id}'...")
    client.tool_runtime.rag_tool.insert(
        documents=documents,
        vector_db_id=vector_db_id,
        chunk_size_in_tokens=int(os.getenv("VECTOR_DB_CHUNK_SIZE", 512)),
    )
    print("end of ingesting")
    return vector_db_id


def run_rag_query(client: LlamaStackClient, model: str, vector_store_id: str, query: str) -> str:
    """Create a RAG agent, run the query, and return the full response text."""
    print(f"Creating RAG agent with model '{model}' and vector store '{vector_store_id}'")
    agent = Agent(
        client,
        model=model,
        instructions=(
            "You are an expert air traffic control supervisor. Use the file search tool to reference FAA AIM procedures when analyzing transcripts."
            "return the top 3 most relevant AIM sections that apply to the question, and quote specific language from the AIM in your answer."
        ),
        sampling_params={"max_tokens": 13000},
        tools=[
            dict(
                name="builtin::rag",
                args={
                    "vector_db_ids": [vector_store_id],
                },
            )
        ],
    )

    session_id = agent.create_session(session_name=f"s{uuid.uuid4().hex}")
    response = agent.create_turn(
        messages=[{"role": "user", "content": query}],
        session_id=session_id,
        stream=False,
    )
    print("RAG query executed, processing response...")
    print(response.output_message.content)
    print("Extracting response text from agent events...")

    return response.output_message.content


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes — transcription
# ---------------------------------------------------------------------------


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
    print("inside of transcribe endpoint")
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

    print(f"Sending transcription request to Whisper model '{WHISPER_MODEL}' with file '{file.filename}'...")
    try:
        result = whisper_client.audio.transcriptions.create(**kwargs)
        granite_client = OpenAI(
            base_url=GRANITE_BASE_URL,
            api_key="YOUR_TOKEN"  # often a bearer token from OpenShift
        )
        clean_result = clean_text(result.text)
        prompt = f"""
        You are an expert in air traffic control (ATC) communications and noisy transcript reconstruction.

        Your task is to transform a messy, error-filled transcript into a clean, readable conversation between a Pilot and an Air Traffic Controller.

        CRITICAL RULES:
        - The input contains transcription errors, repetition, and noise. You MUST clean it aggressively.
        - Remove repeated phrases, duplicate words, and obvious transcription artifacts.
        - Ignore nonsensical fragments (e.g., repeated callsigns, numbers, partial words like "Flattus 5 Flattus 5 Flattus 5").
        - Reconstruct broken sentences into clear, natural aviation communication.
        - You MAY fix obvious transcription mistakes using context (e.g., "Romyocera" → "Romeo Sierra").
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
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.3
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
        "status": "transcribed",
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


@app.get("/shifts")
async def get_shifts(
    page: int = 1,
    page_size: int = 10,
    sort_order: str = "desc",
    facility: str = None,
    status: str = None
):
    # Calculate skip for pagination
    skip = (page - 1) * page_size

    # Build filter dictionary
    filter_dict = {}
    if facility:
        filter_dict["facility"] = facility
    if status:
        filter_dict["status"] = status

    # Build sort dictionary
    sort_dict = {"created_at": 1 if sort_order == "asc" else -1}

    try:
        # Fetch shifts with pagination, sorting, and filtering
        cursor = db["shift"].find(filter_dict).sort(list(sort_dict.items())).skip(skip).limit(page_size)
        shifts = await cursor.to_list(length=page_size)

        # Fetch total count for metadata
        total_shifts = await db["shift"].count_documents(filter_dict)

        # Calculate total pages
        total_pages = (total_shifts + page_size - 1) // page_size

        # Convert MongoDB ObjectIDs to strings
        for shift in shifts:
            shift["_id"] = str(shift["_id"])
            shift["created_at"] = shift["created_at"].isoformat()

        return {
            "shifts": shifts,
            "metadata": {
                "total_shifts": total_shifts,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }
        }
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve shifts: {e}")

# ---------------------------------------------------------------------------
# Routes — shift analysis
# ---------------------------------------------------------------------------


@app.post("/analyze_transcript", response_model=AnalysisResponse)
async def analyze_transcript(req: TranscriptRequest):
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

    try:
        analysis = run_rag_query(llama_client, model, vector_store_id, query)
        doc_update = {"analysis": analysis, "status": "analyzed"}
        doc2 = await db["shift"].update_one({"shift_id": req.shift_id}, {"$set": doc_update})
        print(doc2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

    return AnalysisResponse(
        shift_id=req.shift_id,
        doc=doc2,
        vector_store_id=vector_store_id,
        analysis=analysis,
    )


# ---------------------------------------------------------------------------
# Startup — initialize RAG model and vector store
# ---------------------------------------------------------------------------

try:
    model = build_llm_model(llama_client)
except Exception as e:
    raise HTTPException(status_code=503, detail=f"Failed to connect to Llama Stack: {e}")

try:
    vector_store_id = ingest_urls(llama_client, FAA_AIM_URLS)
except Exception as e:
    raise HTTPException(status_code=502, detail=f"Failed to ingest FAA documents: {e}")
