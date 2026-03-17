from llama_stack_client import LlamaStackClient
from llama_stack_client import Agent, AgentEventLogger
import uuid
import requests

client = LlamaStackClient(base_url="http://localhost:8321")

# Create Documents - download and upload each file
urls = [
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap4_section_2.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_1.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_2.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_3.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_4.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_5.html",
    "https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap6_section_3.html",
]

file_ids = []
print("Downloading and uploading documents...")
for i, url in enumerate(urls):
    filename = url.split("/")[-1]
    print(f"  {i+1}/{len(urls)}: {filename}")

    # Download the content
    response = requests.get(url)
    content = response.text

    # Upload to Llama Stack
    file_obj = client.files.create(
        file=(filename, content.encode('utf-8'), "text/html"),
        purpose="assistants",
    )
    file_ids.append(file_obj.id)

print(f"Uploaded {len(file_ids)} files")

# Create vector store with all files
vector_db_id = f"torchtune_docs_{uuid.uuid4().hex[:8]}"
print(f"Creating vector store: {vector_db_id}")
vector_store = client.vector_stores.create(
    name=vector_db_id,
    file_ids=file_ids,
)
vector_db_id = vector_store.id
print(f"Vector store created: {vector_db_id}")

# Get the model being served - prefer Ollama
models_list = list(client.models.list())
# Filter for LLM models (exclude embedding models)
llm_models = [
    m for m in models_list
    if m.id and not m.id.startswith("sentence-transformers")
]
# Prefer Ollama models
ollama_models = [
    m for m in llm_models
    if "ollama" in m.id
]
model = (ollama_models[0] if ollama_models else llm_models[0]).id
print(f"Using model: {model}")

# Create the RAG agent
print("\nCreating RAG agent...")
rag_agent = Agent(
    client,
    model=model,
    instructions="You are a helpful assistant. Use the file search tool to answer questions as needed.",
    tools=[
        {
            "type": "file_search",
            "vector_store_ids": [vector_db_id],
        }
    ],
)

session_id = rag_agent.create_session(session_name=f"s{uuid.uuid4().hex}")
print(f"Session created: {session_id}")

turns = ["What should the controller do when the plane is too high on approach?"]

print("\nNote: This script will fail due to Llama Stack server routing issues.")
print("Use 'rag_agent_working.py' instead for a working version.\n")

for t in turns:
    print(f"\n{'='*60}")
    print(f"user> {t}")
    print('='*60)
    stream = rag_agent.create_turn(
        messages=[{"role": "user", "content": t}], session_id=session_id, stream=True
    )
    for event in AgentEventLogger().log(stream):
        if hasattr(event, 'print'):
            event.print()
        else:
            # Print text chunks inline without newlines
            print(event, end='', flush=True)
    print()  # Final newline at the end