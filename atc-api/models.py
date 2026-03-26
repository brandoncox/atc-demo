from typing import Optional

from pydantic import BaseModel


class TranscriptRequest(BaseModel):
    shift_id: Optional[str] = None
    doc: Optional[dict] = None
    transcription: Optional[str] = None
    query: Optional[str] = None


class AnalysisResponse(BaseModel):
    shift_id: Optional[str]
    vector_store_id: str
    analysis: str
