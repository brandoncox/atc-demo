import os

from llama_stack_client import LlamaStackClient
from motor.motor_asyncio import AsyncIOMotorClient
from openai import OpenAI

LLAMA_STACK_URL  = os.getenv("LLAMA_STACK_URL",  "http://localhost:8321")
WHISPER_BASE_URL = os.getenv("WHISPER_BASE_URL",  "http://localhost:11434/v1")
WHISPER_MODEL    = os.getenv("WHISPER_MODEL",     "whisper-large-v3-turbo-quantized")
WHISPER_API_KEY  = os.getenv("WHISPER_API_KEY",   "ollama")
GRANITE_BASE_URL = os.getenv("GRANITE_BASE_URL",  "http://localhost:11434/v1")
MONGO_URI        = os.getenv("MONGO_URI",         "mongodb://localhost:27017")

FAA_AIM_URLS = [
    ("https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap4_section_2.html", "text/html"),
    ("https://www.faa.gov/Air_traffic/publications/atpubs/aim_html/chap5_section_1.html", "text/html"),
]

DEFAULT_QUERY_TEMPLATE = (
    "You are an air traffic control shift supervisor reviewing a controller's transcript. "
    "Analyze the following transcript for procedural compliance, communication quality, "
    "and any deviations from FAA standard phraseology or procedures. "
    "Provide a structured assessment with specific findings.\n\n"
    "Transcript:\n{transcription}"
)

llama_client   = LlamaStackClient(base_url=LLAMA_STACK_URL)
whisper_client = OpenAI(base_url=WHISPER_BASE_URL, api_key=WHISPER_API_KEY)
db             = AsyncIOMotorClient(MONGO_URI)["atc"]
