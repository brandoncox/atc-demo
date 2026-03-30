import os

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import db, llama_client
from rag import build_llm_model, register_slack_mcp
import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db["shift"].create_index("shift_id", unique=True, sparse=True)
    try:
        await asyncio.to_thread(register_slack_mcp, llama_client)
        app.state.model = await asyncio.to_thread(build_llm_model, llama_client)
        print("RAG backend initialized successfully. Trigger POST /ingest to load FAA documents.")
    except Exception as e:
        print(f"WARNING: RAG initialization failed: {e}. /analyze_transcript will be unavailable until resolved.")
        app.state.model = None
    app.state.vector_store_id = None
    yield


app = FastAPI(title="ATC API", version="1.0.0", lifespan=lifespan)

_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
