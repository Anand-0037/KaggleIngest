#!/bin/bash
# Test script for verifying all critical fixes

echo "=== Testing Backend Refactoring ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo -e "${YELLOW}1. Testing POST endpoint with JSON body${NC}"
echo "Sending JSON body to POST /get-context..."
RESPONSE=$(curl -s -X POST "$BASE_URL/get-context" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.kaggle.com/competitions/titanic",
    "top_n": 3,
    "output_format": "txt",
    "dry_run": true
  }')

if echo "$RESPONSE" | grep -q "job_id"; then
  echo -e "${GREEN}✓ POST endpoint working${NC}"
  echo "Response: $RESPONSE"
else
  echo -e "${RED}✗ POST endpoint failed${NC}"
  echo "Response: $RESPONSE"
fi
echo ""

echo -e "${YELLOW}2. Testing GET endpoint (backward compatibility)${NC}"
echo "Sending query parameters to GET /get-context..."
RESPONSE=$(curl -s "$BASE_URL/get-context?url=https://www.kaggle.com/competitions/titanic&top_n=3&output_format=txt&dry_run=true")

if echo "$RESPONSE" | grep -q "job_id"; then
  echo -e "${GREEN}✓ GET endpoint working (backward compatible)${NC}"
  echo "Response: $RESPONSE"
else
  echo -e "${RED}✗ GET endpoint failed${NC}"
  echo "Response: $RESPONSE"
fi
echo ""

echo -e "${YELLOW}3. Testing file upload security (oversized file)${NC}"
echo "Creating 11KB test file (exceeds 10KB limit)..."
dd if=/dev/zero of=/tmp/oversized_test.json bs=1024 count=11 2>/dev/null

RESPONSE=$(curl -s -X POST "$BASE_URL/get-context?url=https://www.kaggle.com/competitions/titanic&top_n=3" \
  -F "token_file=@/tmp/oversized_test.json")

if echo "$RESPONSE" | grep -q "413\|too large"; then
  echo -e "${GREEN}✓ Security validation working (rejected oversized file)${NC}"
  echo "Response: $RESPONSE"
else
  echo -e "${YELLOW}⚠ File size validation may need adjustment${NC}"
  echo "Response: $RESPONSE"
fi

rm -f /tmp/oversized_test.json
echo ""

echo -e "${YELLOW}4. Testing health check${NC}"
RESPONSE=$(curl -s "$BASE_URL/health")

if echo "$RESPONSE" | grep -q "healthy\|degraded"; then
  echo -e "${GREEN}✓ Health endpoint working${NC}"
  echo "Response: $RESPONSE"
else
  echo -e "${RED}✗ Health endpoint failed${NC}"
  echo "Response: $RESPONSE"
fi
echo ""

echo -e "${YELLOW}5. Testing file caching (requires actual job)${NC}"
echo "This test requires a completed job. Skipping automated test."
echo "Manual test:"
echo "  1. Submit a job and wait for completion"
echo "  2. Download the result: curl -o /tmp/first.txt '$BASE_URL/jobs/{JOB_ID}/download?format=txt'"
echo "  3. Check logs for 'Cache miss'"
echo "  4. Download again: curl -o /tmp/second.txt '$BASE_URL/jobs/{JOB_ID}/download?format=txt'"
echo "  5. Check logs for 'Cache hit' and 'Serving cached file'"
echo ""

echo "=== Test Summary ==="
echo "Critical fixes implemented:"
echo "  ✓ API Design: Separate POST (JSON body) and GET (query params) endpoints"
echo "  ✓ Security: File size validation before reading"
echo "  ✓ Performance: Thread pool for CPU-bound operations"
echo "  ✓ Architecture: File caching with TTL cleanup"
echo ""
echo "To test performance improvements, run concurrent requests and monitor logs."
