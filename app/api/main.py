"""
Main FastAPI application for CL-SRS
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
from dotenv import load_dotenv

from app.api.database import init_db
from app.api.storage import storage
from app.api.services.authoring import AuthoringService
from app.api.services.ingestion import IngestionService
from app.api.services.grading import GradingService
from app.api.models_v1 import Concept, Item, AttemptLog, ASRData

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="CL-SRS API",
    description="Concept-Level Spaced Repetition System",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
authoring_service = AuthoringService()
ingestion_service = IngestionService()
grading_service = GradingService()


# Request/Response Models
class IngestURLRequest(BaseModel):
    url: str = Field(..., description="URL to fetch and extract text from")


class IngestURLResponse(BaseModel):
    text: str
    meta: Dict[str, Any]
    status: str


class AuthorQuestionsRequest(BaseModel):
    text: str = Field(..., description="Source text to generate questions from")
    system_prompt_id: str = Field(default="authoring_v1", description="Prompt version to use")
    concept_id: Optional[str] = Field(None, description="Existing concept to add items to")


class AuthorQuestionsResponse(BaseModel):
    concept_ids: List[str]
    item_ids: List[str]
    status: str
    error: Optional[str] = None


class GradeAttemptRequest(BaseModel):
    item_id: str
    audio_blob: Optional[bytes] = None
    text: Optional[str] = None
    asr_payload: Optional[Dict[str, Any]] = None
    latency_ms: int


class GradeAttemptResponse(BaseModel):
    outcome: str
    score_adj: int
    explanation_for_user: str
    next_review_eta: datetime


class DueCardsRequest(BaseModel):
    now: Optional[datetime] = None


class DueCardsResponse(BaseModel):
    items: List[Dict[str, Any]]


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()
    print("CL-SRS API started successfully")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# Main endpoints
@app.post("/ingest_url", response_model=IngestURLResponse)
async def ingest_url(request: IngestURLRequest):
    """
    Fetch and extract main text content from a URL
    """
    result = await ingestion_service.ingest_url(request.url)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    
    return IngestURLResponse(
        text=result["text"],
        meta=result["meta"],
        status=result["status"]
    )


class IngestTextRequest(BaseModel):
    text: str = Field(..., description="Text content to process")


@app.post("/ingest_text", response_model=IngestURLResponse)
async def ingest_text(request: IngestTextRequest):
    """
    Process raw text input (alternative to URL)
    """
    result = await ingestion_service.ingest_text(request.text)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    
    return IngestURLResponse(
        text=result["text"],
        meta=result["meta"],
        status=result["status"]
    )


@app.post("/author_questions", response_model=AuthorQuestionsResponse)
async def author_questions(request: AuthorQuestionsRequest):
    """
    Generate concepts and items from source text using LLM
    """
    result = await authoring_service.author_from_text(
        text=request.text,
        concept_id=request.concept_id
    )
    
    if result["status"] == "error":
        return AuthorQuestionsResponse(
            concept_ids=[],
            item_ids=[],
            status="error",
            error=result.get("error", "Unknown error")
        )
    
    return AuthorQuestionsResponse(
        concept_ids=result["concept_ids"],
        item_ids=result["item_ids"],
        status=result["status"]
    )


@app.post("/grade_attempt", response_model=GradeAttemptResponse)
async def grade_attempt(request: GradeAttemptRequest):
    """
    Grade a learner's attempt (voice or text)
    """
    # Get the item
    item = await storage.get_item(request.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Prepare ASR data if provided
    asr_data = None
    if request.asr_payload:
        asr_data = ASRData(**request.asr_payload)
    
    # Grade the attempt
    result = await grading_service.grade_attempt(
        item=item,
        audio_or_text=request.text,
        asr_data=asr_data,
        latency_ms=request.latency_ms
    )
    
    return GradeAttemptResponse(
        outcome=result["outcome"],
        score_adj=result["score_adj"],
        explanation_for_user=result["explanation_for_user"],
        next_review_eta=result["next_review_eta"]
    )


@app.get("/due_cards", response_model=DueCardsResponse)
async def get_due_cards(now: Optional[datetime] = None):
    """
    Get cards that are due for review
    """
    if now is None:
        now = datetime.utcnow()
    
    due_items = await storage.get_due_items(now)
    
    # Format items for response
    items = []
    for item in due_items:
        items.append({
            "item_id": item.id,
            "concept_id": item.concept_id,
            "prompt": item.prompt,
            "kc": item.kc.value if hasattr(item.kc, 'value') else item.kc
        })
    
    return DueCardsResponse(items=items)


@app.get("/concepts")
async def get_concepts():
    """
    Get all concepts
    """
    concepts = await storage.get_all_concepts()
    return {"concepts": [c.dict() for c in concepts]}


@app.get("/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """
    Get a specific concept
    """
    concept = await storage.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept.dict()


@app.get("/concepts/{concept_id}/items")
async def get_concept_items(concept_id: str):
    """
    Get all items for a concept
    """
    items = await storage.get_items_by_concept(concept_id)
    return {"items": [i.dict() for i in items]}


@app.get("/items/{item_id}")
async def get_item(item_id: str):
    """
    Get a specific item
    """
    item = await storage.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item.dict()


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload
    )