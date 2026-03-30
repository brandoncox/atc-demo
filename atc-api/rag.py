import json
import os
import re
import uuid

from fastapi import HTTPException
from llama_stack_client import LlamaStackClient, RAGDocument, Agent

SLACK_MCP_URL       = os.getenv("SLACK_MCP_URL", "http://slack-mcp-server:80/sse")
SAFETY_THRESHOLD    = int(os.getenv("SAFETY_SCORE_THRESHOLD", 75))


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


def register_slack_mcp(client: LlamaStackClient) -> None:
    """Register the Slack MCP toolgroup with LlamaStack if not already registered."""
    registered = {tg.identifier for tg in client.toolgroups.list()}
    if "mcp::slack" in registered:
        print("mcp::slack toolgroup already registered, skipping.")
        return
    print(f"Registering mcp::slack toolgroup at {SLACK_MCP_URL}...")
    client.toolgroups.register(
        toolgroup_id="mcp::slack",
        provider_id="model-context-protocol",
        mcp_endpoint={"uri": SLACK_MCP_URL},
    )
    print("mcp::slack toolgroup registered successfully.")


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


def _parse_safety_score(text: str) -> int:
    """Extract the numeric safety score from the agent's JSON response."""
    try:
        # Try to find a JSON block first
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return int(data.get("score", 0))
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: grab the first integer in the response
    match = re.search(r'\b(\d{1,3})\b', text)
    return int(match.group(1)) if match else 0


def _format_shift_context(shift_data: dict) -> str:
    """Render shift metadata into a readable block for the prompt."""
    start   = shift_data.get("start_time", "unknown")
    end     = shift_data.get("end_time", "unknown")
    lines = [
        f"- Controller ID:     {shift_data.get('controller_id', 'unknown')}",
        f"- Facility:          {shift_data.get('facility', 'unknown')}",
        f"- Position:          {shift_data.get('position', 'unknown')}",
        f"- Shift type:        {shift_data.get('schedule_type', 'unknown')}",
        f"- Start time:        {start}",
        f"- End time:          {end}",
        f"- Avg traffic count: {shift_data.get('traffic_count_avg', 'unknown')}",
    ]
    return "\n".join(lines)


def run_rag_query(
    client: LlamaStackClient,
    model: str,
    vector_store_id: str,
    query: str,
    shift_data: dict | None = None,
) -> str:
    """
    Multi-turn agent pipeline:
      Turn 1 — RAG analysis of transcript against FAA AIM procedures.
      Turn 2 — Safety score (0-100) based on transcript findings + shift metadata.
      Turn 3 — Slack notification via MCP if score >= SAFETY_THRESHOLD.
    """
    print(f"Creating RAG agent with model '{model}' and vector store '{vector_store_id}'")
    agent = Agent(
        client,
        model=model,
        instructions=(
            "You are an expert air traffic control supervisor. Use the file search tool to reference FAA AIM procedures when analyzing transcripts."
            "return the top 3 most relevant AIM sections that apply to the question, and quote specific language from the AIM in your answer."
        ),
        sampling_params={"max_tokens": 4096},
        tool_config={"tool_choice":"auto"},
        tools=[
            dict(
                name="builtin::rag",
                args={"vector_db_ids": [vector_store_id]},
            ),"mcp::slack",
        ],
    )

    session_id = agent.create_session(session_name=f"s{uuid.uuid4().hex}")

    # ------------------------------------------------------------------
    # Turn 1 — FAA AIM procedure analysis
    # ------------------------------------------------------------------
    print("=== Turn 1: FAA Procedure Analysis ===")
    try:

        print(f"Query:\n{query}\n")
        response1 = agent.create_turn(
            messages=[{"role": "user", "content": query}],
            session_id=session_id,
            stream=False,
        )
        analysis = response1.output_message.content
        print(analysis)
    except Exception as e:
        print(f"ERROR: Turn 1 (procedure analysis) failed: {e}")
        raise RuntimeError(f"Turn 1 (procedure analysis) failed: {e}") from e

    # ------------------------------------------------------------------
    # Turn 2 — Safety score
    # ------------------------------------------------------------------
    shift_block = _format_shift_context(shift_data) if shift_data else "No shift metadata available."
    safety_prompt = (
        "Based on your procedure analysis above and the shift data below, "
        "compute a safety score from 0 (no risk) to 100 (critical risk) "
        "for this controller.\n\n"
        f"Shift data:\n{shift_block}\n\n"
        "Consider: communication errors, non-standard phraseology, hours on position, "
        "traffic load, shift type (overtime/regular), time-of-day fatigue risk, and "
        "any deviations identified in your analysis.\n\n"
        'Return ONLY a JSON object in this format: '
        '{"score": <0-100>, "factors": ["...", "..."], "summary": "one sentence"}'
    )

    print("=== Turn 2: Safety Score ===")
    safety_score = 0
    try:
        response2 = agent.create_turn(
            messages=[{"role": "user", "content": safety_prompt}],
            session_id=session_id,
            stream=False,
        )
        safety_text = response2.output_message.content
        print(safety_text)
        safety_score = _parse_safety_score(safety_text)
        print(f"Parsed safety score: {safety_score} (threshold: {SAFETY_THRESHOLD})")
    except Exception as e:
        print(f"WARNING: Turn 2 (safety score) failed: {e}. Skipping Slack alert.")

    # ------------------------------------------------------------------
    # Turn 3 — Slack alert if score exceeds threshold
    # ------------------------------------------------------------------

    controller_id = shift_data.get("controller_id", "Unknown") if shift_data else "Unknown"
    facility      = shift_data.get("facility",      "Unknown") if shift_data else "Unknown"

    slack_prompt = (
        f"The safety score for controller {controller_id} at {facility} is "
        f"{safety_score}/100, which meets or exceeds the alert threshold of {SAFETY_THRESHOLD}.\n\n"
        "Send the following message with the summarization to the demos channel on Slack with a tool call:\n"
        f"- Controller: {controller_id}\n"
        f"- Facility: {facility}\n"
        f"- Safety score: {safety_score}/100\n"
        "- Key risk factors: (from your analysis)\n"
        "- Recommendation: Evaluate whether this controller should be rotated out of their current shift."
    )

    print("=== Turn 3: Slack Supervisor Alert ===")
    try:
        response3 = agent.create_turn(
            messages=[{"role": "user", "content": "Send a message with the summarization to the demos channel on Slack."}],
            session_id=session_id,
            stream=False,
        )
        print(response3.output_message.content)
    except Exception as e:
        print(f"WARNING: Turn 3 (Slack alert) failed: {e}")

    return analysis + safety_text
