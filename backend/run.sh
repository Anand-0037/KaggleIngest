#!/bin/bash



# Start FastAPI application in the foreground
echo "Starting FastAPI app..."
uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}
