import os
import uuid
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from llama_stack_client import RAGDocument
from llama_stack_client import LlamaStackClient, Agent, AgentEventLogger

LLAMA_STACK_URL = os.getenv("LLAMA_STACK_URL", "http://localhost:8321")

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

client = LlamaStackClient(base_url=LLAMA_STACK_URL)
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
    documents = []
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
    # vector_store = client.vector_stores.create(
    #     name=vector_db_id,
    #     file_ids=file_ids,
    # )
    print("end of ingesting")
    return vector_db_id


def run_rag_query(client: LlamaStackClient, model: str, vector_store_id: str, query: str) -> str:
    """Create a RAG agent, run the query, and return the full response text."""
    print(f"Creating RAG agent with model '{model}' and vector store '{vector_store_id}'")
    agent = Agent(
        client,
        model=model,
        instructions=(
            "You are an expert air traffic control supervisor. Use the file search tool to reference FAA AIM procedures when analyzing transcripts." \
            "return the top 3 most relevant AIM sections that apply to the question, and quote specific language from the AIM in your answer." \
        ),
        sampling_params={"max_tokens": 13000},
        tools=[
            dict(
                name="builtin::rag",
                args={
                "vector_db_ids": [vector_store_id],  # list of IDs of document collections to consider during retrieval
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
    chunks = []
    for event in AgentEventLogger().log(response):
        if hasattr(event, "text"):
            chunks.append(event.text)
        elif isinstance(event, str):
            chunks.append(event)

    print("RAG query completed.")
    print(f"Full response:\n{''.join(chunks)}")
    return "".join(chunks).strip()


@app.post("/analyze_transcript", response_model=AnalysisResponse)
async def analyze_transcript(req: TranscriptRequest):
    
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

try:
    model = build_llm_model(client)
except Exception as e:
    raise HTTPException(status_code=503, detail=f"Failed to connect to Llama Stack: {e}")

try:
    vector_store_id = ingest_urls(client, FAA_AIM_URLS)
except Exception as e:
    raise HTTPException(status_code=502, detail=f"Failed to ingest FAA documents: {e}")

