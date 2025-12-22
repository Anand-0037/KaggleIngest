#!/bin/bash
# Integration test: Verify frontend-backend communication

set -e

echo "=== Integration Test: Frontend ↔ Backend ==="

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend not running. Start with: cd kaggleIngest && uvicorn app:app --reload"
    exit 1
fi

echo "✓ Backend is running"

# Test 1: POST with JSON body (no file)
echo ""
echo "Test 1: POST /get-context with JSON body"
RESPONSE=$(curl -s -X POST http://localhost:8000/get-context \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.kaggle.com/competitions/titanic",
    "top_n": 2,
    "output_format": "txt",
    "dry_run": true
  }')

if echo "$RESPONSE" | grep -q "job_id"; then
  echo "✓ POST endpoint accepts JSON body"
else
  echo "❌ POST endpoint failed"
  echo "Response: $RESPONSE"
  exit 1
fi

# Test 2: GET endpoint (backward compatibility)
echo ""
echo "Test 2: GET /get-context with query params"
RESPONSE=$(curl -s "http://localhost:8000/get-context?url=https://www.kaggle.com/competitions/titanic&top_n=2&output_format=txt&dry_run=true")

if echo "$RESPONSE" | grep -q "job_id"; then
  echo "✓ GET endpoint still works (backward compatible)"
else
  echo "❌ GET endpoint failed"
  echo "Response: $RESPONSE"
  exit 1
fi

# Test 3: Frontend build
echo ""
echo "Test 3: Frontend build"
cd /home/anand/work/backend/kaggleIngest-ui
if npm run build > /dev/null 2>&1; then
  echo "✓ Frontend builds successfully"
else
  echo "❌ Frontend build failed"
  exit 1
fi

echo ""
echo "=== All Integration Tests Passed ✓ ==="
echo ""
echo "Frontend and backend are properly integrated:"
echo "  • POST accepts JSON body (new API contract)"
echo "  • GET accepts query params (backward compatible)"
echo "  • Frontend builds without errors"
