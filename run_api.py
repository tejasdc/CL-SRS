#!/usr/bin/env python
"""
Run the CL-SRS API server (simplified version for Python 3.13)
"""
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"  # Disabled auto-reload to prevent data loss
    
    print(f"Starting CL-SRS API (Simplified) on {host}:{port}")
    print(f"Reload: {reload}")
    print(f"OpenAPI docs: http://localhost:{port}/docs")
    
    uvicorn.run(
        "app.api.main_simple:app",  # Use simplified main
        host=host,
        port=port,
        reload=reload
    )