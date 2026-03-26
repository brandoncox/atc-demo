import os
import re
import uuid

from fastapi import HTTPException
from llama_stack_client import LlamaStackClient, RAGDocument, Agent


def clean_text(text: str) -> str:
    text = re.sub(r'\b(\w+)( \1\b)+', r'\1', text)
    text = re.sub(r'(\d+\.){2,}', '', text)
    return text


def build_llm_model(client: LlamaStackClient) -> str:
    print("Fetching available models from Llama Stack...")
    models = list(client.models.list())
    print(f"Total models available: {len(models)}")

    llm_models = [m for m in models if m.identifier and not m.identifier.startswith("sentence-transformers")]
    if not llm_models:
        raise HTTPException(status_code=503, detail="No LLM models available on Llama Stack server")

    print(f"Available LLM models: {[m.identifier for m in llm_models]}")
    print(llm_models[1].identifier)
    return llm_models[1].identifier


def ingest_urls(client: LlamaStackClient, urls: list) -> str:
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
        for i, (url, url_type) in enumerate(urls)
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
                args={"vector_db_ids": [vector_store_id]},
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
    return response.output_message.content
