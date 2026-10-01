import os
import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting AI Skin Specialist Web Dashboard...")
    print("Open in browser: http://localhost:8000")
    print("=" * 60)
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=True)
