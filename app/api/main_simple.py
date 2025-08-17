"""
Simplified FastAPI application for CL-SRS
Compatible with Python 3.13
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
from dotenv import load_dotenv

# Use simplified models
from app.api.models_simple import Concept, Item, AttemptLog, ASRData
from app.api.storage import storage
from app.api.services.authoring import AuthoringService
from app.api.services.ingestion import IngestionService

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
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
authoring_service = AuthoringService()
ingestion_service = IngestionService()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Main endpoints
@app.post("/ingest_url")
async def ingest_url(data: Dict[str, Any]):
    """
    Fetch and extract main text content from a URL
    """
    url = data.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    result = await ingestion_service.ingest_url(url)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.post("/ingest_text")
async def ingest_text(data: Dict[str, Any]):
    """
    Process raw text input (alternative to URL)
    """
    text = data.get("text", "")
    result = await ingestion_service.ingest_text(text)
    
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.post("/author_questions")
async def author_questions(data: Dict[str, Any]):
    """
    Generate concepts and items from source text using LLM
    """
    text = data.get("text", "")
    print(f"[API] /author_questions called with text length: {len(text)}")
    
    try:
        result = await authoring_service.author_from_text(text)
        print(f"[API] Authoring result: {result}")
        return result
    except Exception as e:
        print(f"[API] Error in author_questions: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "concept_ids": [],
            "item_ids": [],
            "status": "error",
            "error": str(e)
        }


@app.post("/grade_attempt")
async def grade_attempt(data: Dict[str, Any]):
    """
    Grade a learner's attempt using the full grading pipeline
    """
    item_id = data.get("item_id")
    text = data.get("text", "")
    latency_ms = data.get("latency_ms", 0)
    
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id is required")
    
    # Get the item from storage
    item = await storage.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Use the actual grading service
    from app.api.services.grading import GradingService
    grading_service = GradingService()
    
    try:
        result = await grading_service.grade_attempt(
            item=item,
            audio_or_text=text,
            latency_ms=latency_ms
        )
        print(f"[API] Grading result: {result}")
        return result
    except Exception as e:
        # Fallback to simple grading if the full service fails
        from datetime import timedelta
        print(f"[API] Grading error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "outcome": "fail",
            "score_adj": 0,
            "explanation_for_user": f"Grading error: {str(e)}",
            "next_review_eta": (datetime.utcnow() + timedelta(days=1)).isoformat()
        }


@app.get("/due_cards")
async def get_due_cards():
    """
    Get cards that are due for review
    """
    print(f"[API] Getting due cards...")
    print(f"[API] Total items in storage: {len(storage.items)}")
    
    due_items = await storage.get_due_items()
    print(f"[API] Found {len(due_items)} due items")
    
    # Format items for response
    items = []
    for item in due_items:
        items.append({
            "item_id": item.id,
            "concept_id": item.concept_id,
            "prompt": item.prompt,
            "kc": item.kc
        })
    
    print(f"[API] Returning {len(items)} items to client")
    return {"items": items}


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
    
    uvicorn.run(
        app,
        host=host,
        port=port
    )