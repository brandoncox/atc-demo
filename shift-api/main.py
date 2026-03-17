import os
import uuid
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from llama_stack_client import LlamaStackClient, Agent, AgentEventLogger

LLAMA_STACK_URL = os.getenv("LLAMA_STACK_URL", "http://localhost:8321")

FAA_AIM_URLS = [
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap4_section_2.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_1.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_2.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_3.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_4.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_5.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap6_section_3.html",
]

DEFAULT_QUERY_TEMPLATE = (
    "You are an air traffic control shift supervisor reviewing a controller's transcript. "
    "Analyze the following transcript for procedural compliance, communication quality, "
    "and any deviations from FAA standard phraseology or procedures. "
    "Provide a structured assessment with specific findings.\n\n"
    "Transcript:\n{transcription}"
)

app = FastAPI(title="Shift Analysis API", version="1.0.0")


class TranscriptRequest(BaseModel):
    shift_id: Optional[str] = None
    controller_id: Optional[str] = None
    facility: Optional[str] = None
    transcription: str
    query: Optional[str] = None  # Override the default analysis query


class AnalysisResponse(BaseModel):
    shift_id: Optional[str]
    vector_store_id: str
    analysis: str


def build_llm_model(client: LlamaStackClient) -> str:
    models = list(client.models.list())
    llm_models = [m for m in models if m.id and not m.id.startswith("sentence-transformers")]
    ollama_models = [m for m in llm_models if "ollama" in m.id]
    if not llm_models:
        raise HTTPException(status_code=503, detail="No LLM models available on Llama Stack server")
    return (ollama_models[0] if ollama_models else llm_models[0]).id


def ingest_urls(client: LlamaStackClient, urls: list[str]) -> str:
    """Download FAA AIM pages, upload to Llama Stack, and return a vector store ID."""
    file_ids = []
    for url in urls:
        filename = url.split("/")[-1]
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        file_obj = client.files.create(
            file=(filename, resp.content, "text/html"),
            purpose="assistants",
        )
        file_ids.append(file_obj.id)

    vector_store = client.vector_stores.create(
        name=f"aim_docs_{uuid.uuid4().hex[:8]}",
        file_ids=file_ids,
    )
    return vector_store.id


def run_rag_query(client: LlamaStackClient, model: str, vector_store_id: str, query: str) -> str:
    """Create a RAG agent, run the query, and return the full response text."""
    agent = Agent(
        client,
        model=model,
        instructions=(
            "You are an expert air traffic control supervisor. "
            "Use the file search tool to reference FAA AIM procedures when analyzing transcripts."
        ),
        tools=[
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
            }
        ],
    )

    session_id = agent.create_session(session_name=f"s{uuid.uuid4().hex}")
    stream = agent.create_turn(
        messages=[{"role": "user", "content": query}],
        session_id=session_id,
        stream=True,
    )

    chunks = []
    for event in AgentEventLogger().log(stream):
        if hasattr(event, "text"):
            chunks.append(event.text)
        elif isinstance(event, str):
            chunks.append(event)

    return "".join(chunks).strip()


@app.post("/analyze_transcript", response_model=AnalysisResponse)
async def analyze_transcript(req: TranscriptRequest):
    client = LlamaStackClient(base_url=LLAMA_STACK_URL)

    print(client)

    try:
        model = build_llm_model(client)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to connect to Llama Stack: {e}")

    try:
        vector_store_id = ingest_urls(client, FAA_AIM_URLS)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to ingest FAA documents: {e}")

    query = req.query or DEFAULT_QUERY_TEMPLATE.format(transcription=req.transcription)

    try:
        analysis = run_rag_query(client, model, vector_store_id, query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

    return AnalysisResponse(
        shift_id=req.shift_id,
        vector_store_id=vector_store_id,
        analysis=analysis,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
