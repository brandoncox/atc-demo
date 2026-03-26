import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import db, llama_client, FAA_AIM_URLS
from rag import build_llm_model, ingest_urls
import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db["shift"].create_index("shift_id", unique=True, sparse=True)
    app.state.model = build_llm_model(llama_client)
    app.state.vector_store_id = ingest_urls(llama_client, FAA_AIM_URLS)
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
