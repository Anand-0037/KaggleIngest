# KaggleIngest

> **The High-Performance Bridge Between Kaggle Data and LLMs.**

KaggleIngest transforms complex Kaggle competitions, datasets, and notebooks into token-optimized context for AI assistants. It eliminates noise and intelligently ranks high-signal implementation patterns to help you win competitions faster.

## SaaS-First Architecture

We've evolved. KaggleIngest is now a production-ready SaaS platform built on a high-performance **PostgreSQL-as-Everything** architecture.

- **Postgres-Only Stack**: Replaced SQLite/Redis with a unified PostgreSQL engine for state management, ranked search, and audit-compliant caching.
- **API-First Security**: Robust `X-API-Key` authentication with tiered credit management and usage tracking.
- **High-Performance Caching**: `UNLOGGED` caching layer for maximum write throughput during ingestion, ensuring zero-latency "hits" for popular competitions.
- **Multi-Strategy Search**: full-text search (FTS) combined with trigram similarity for typo-tolerant, ranked results.

## Core Capabilities

- **Smart Context Ranking**: Custom scoring algorithm (`Log(Upvotes) * TimeDecay`) prioritizes recent, high-quality solution patterns.
- **Token-Oriented Object Notation (TOON)**: A proprietary format that reduces token consumption while preserving structural metadata for LLMs.
- **Dual-Track Ingestion**: Instant context for cached competitions; automated background fetching for new ones.
- **Robust Parsing**: Hardened support for legacy `nbformat`, multi-encoding CSVs, and malformed datasets.

---

## API Reference

Base URL: `http://localhost:8000` (Local) | `https://api.kaggleingest.com` (Prod)

### 1. Authentication
Create an account to get your personal `ki_...` API key.
- `POST /auth/signup`
- `GET /auth/me` (Check credits/tier)

### 2. Search Competitions
Ranked search across the entire Kaggle index.
- `GET /search?query=titanic`

### 3. Get Competition Context
Dual-track endpoint. Returns context instantly if cached, otherwise starts a background fetch.
- `GET /competitions/{slug}`
*Headers: `X-API-Key: YOUR_KEY`*

---

## Usage Examples

### CLI (curl)
```bash
# 1. Signup and save API key
API_KEY=$(curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com", "password":"securepass123"}' | jq -r .api_key)

# 2. Search for a competition
curl "http://localhost:8000/search?query=house-prices" -H "X-API-Key: $API_KEY"

# 3. Get Context (Titanic)
curl "http://localhost:8000/competitions/titanic" -H "X-API-Key: $API_KEY"
```

### Python Integration
```python
import requests

API_KEY = "ki_..."
BASE_URL = "http://localhost:8000"

def get_kaggle_context(slug):
    headers = {"X-API-Key": API_KEY}
    response = requests.get(f"{BASE_URL}/competitions/{slug}", headers=headers)

    data = response.json()
    if data["status"] == "processing":
        print("Metadata is being fetched. Check back in 60 seconds.")
    else:
        return data["formatted_output"]
```

---

## LLM System Prompt (TOON v2.0)

Copy this into your LLM prompt to help it interpret TOON results:

```text
You are analyzing Kaggle competition context in TOON (Token-Oriented Object Notation) v2.0.
Structure:
- metadata: = Competition info (title, url, category, prize)
- schema: = Dataset column definitions
- sample_rows: = Data preview rows
- notebooks[N]{fields}: = Top N notebooks with specified fields
- content: = Full notebook text/code content

Guidelines:
1. Prioritize patterns found in higher-ranked notebooks (top of list).
2. Synthesize feature engineering techniques across multiple implementations.
3. Validate your proposed models against the provided schema and sample data.
```

---

## Get Started Locally

1. **Clone & Install**:
   ```bash
   git clone https://github.com/Anand-0037/KaggleIngest
   cd KaggleIngest
   ```

2. **Backend Setup**:
   ```bash
   cd backend && uv sync
   cp .env.example .env # Add your Postgres and Kaggle keys
   uvicorn backend.app:app --reload
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend && npm install
   npm run dev
   ```

---
© 2026 KaggleIngest | Bridge the Context Gap.
