# KaggleIngest

> **The Bridge Between Kaggle Data and LLMs.**

KaggleIngest transforms complex Kaggle competitions, datasets, and notebooks into high-quality, token-optimized context for Large Language Models. It solves the "context window" problem by intelligently ranking content and stripping noise.

## 🚀 Core Capabilities

- **🧠 Smart Context Ranking**: Uses a custom scoring algorithm (`Log(Upvotes) * TimeDecay`) to prioritize high-quality, recent implementation patterns over stale kernels.
- **⚡ Async Scalability**: Built on a robust `Redis` + `arq` backend to handle massive datasets and concurrent ingestion jobs without timeout risks.
- **📄 Multi-Format Output**:
  - **`.toon` (Recommended)**: Token Optimized Object Notation. A JSON-like format that uses ~40% fewer tokens than standard JSON to represent code cells, markdown, and metadata.
  - **`.txt`**: Plain text, human-readable summary.
  - **`.md`**: Markdown with syntax highlighting support.
- **🛡️ Robust Ingestion**: Hardened parsers for legacy `nbformat` v3, multi-encoding CSVs (UTF-8/Latin-1/CP1252), and resilient error handling for malformed notebooks.

---

## 📚 API Reference

Base URL: `http://localhost:8000` (or deployed URL)

### 1. Submit Ingestion Job

`POST /get-context`

Initiates an asynchronous background job to fetch, parse, and rank content.

**Payload:**

```json
{
  "url": "https://www.kaggle.com/competitions/titanic",
  "top_n": 20, // Optional: Max notebooks to process (Default: 10)
  "output_format": "toon", // Optional: 'txt', 'toon', 'md' (Default: 'txt')
  "dry_run": false // Optional: Fetch metadata only (Default: false)
}
```

**Response:**

```json
{
  "job_id": "35f21fae4ddb463b9ff383c33b3346ab",
  "status": "queued",
  "message": "Job submitted successfully. Poll /jobs/{job_id} for status."
}
```

### 2. Poll Job Status

`GET /jobs/{job_id}`

Check the progress of a submitted job.

**Response (Processing):**

```json
{
  "job_id": "35f21fae...",
  "status": "in_progress",
  "status_data": {
    "progress": {
      "total": 10,
      "current": 4,
      "percent": 40
    }
  },
  "result": null
}
```

**Response (Complete):**

```json
{
  "job_id": "35f21fae...",
  "status": "complete",
  "result": {
    "metadata": {
      "title": "Titanic - Machine Learning from Disaster",
      "url": "https://www.kaggle.com/competitions/titanic"
    },
    "stats": {
      "total_requested": 10,
      "successful_downloads": 9,
      "failed_downloads": 1,
      "failed_notebooks": [
        {
          "ref": "user/notebook-slug",
          "title": "Notebook Title",
          "error": "No .ipynb file found"
        }
      ],
      "elapsed_time": 4.52
    }
  }
}
```

### 3. Download Result

`GET /jobs/{job_id}/download`

Stream the final processed file.
_Query Parameter:_ `format` (optional) - Override the originally requested format (e.g., `?format=md`).

---

## 💻 Usage Examples

### Python Client

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# 1. Submit Job
payload = {"url": "https://www.kaggle.com/competitions/titanic", "output_format": "toon"}
job = requests.post(f"{BASE_URL}/get-context", json=payload).json()
job_id = job["job_id"]

# 2. Poll until complete
while True:
    status = requests.get(f"{BASE_URL}/jobs/{job_id}").json()
    if status["status"] in ["complete", "failed"]:
        break
    time.sleep(2)

# 3. Download
if status["status"] == "complete":
    content = requests.get(f"{BASE_URL}/jobs/{job_id}/download").text
    print(content)
```

### CLI (curl)

```bash
# Submit
JOB_ID=$(curl -X POST http://localhost:8000/get-context \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.kaggle.com/competitions/titanic"}' | jq -r .job_id)

# Download (After waiting)
curl -OJO "http://localhost:8000/jobs/$JOB_ID/download?format=md"
```

---

## 🏗️ Architecture

```
kaggleIngest/
├── kaggleIngest-ui/      # React Frontend (Vite + CSS Modules)
│   ├── src/components/   # UI Components via Atomic Design
│   └── tests/            # Playwright E2E Tests
├── core/                 # Core Logic
│   ├── toon_encoder.py   # TOON encoder implementation
│   └── jobs.py           # Job processing & Pydantic models
├── services/             # Business Logic Layer
│   ├── kaggle_service.py # Thread-safe Kaggle API wrapper
│   └── notebook_service.py # Orchestrator for concurrency
├── app.py                # FastAPI Application
├── worker.py             # ARQ Worker & Cron Jobs
└── config.py             # Configuration & Environment
```

## 🔒 Security

- **Ephemeral Credentials**: User uploads (`kaggle.json`) are processed in memory and never stored permanently.
- **Validation**: Strict file size limits and type checks on all inputs.
- **Sandboxing**: Dockerized deployment ensures isolation.

## 📄 License

MIT License. Open source and free to use.

---

## 🌟 New Features

### Auto-Ingestion

The application now supports automatic ingestion via URL modification.

1.  **Modify the URL**: Change `kaggle.com` to `localhost:5173` (e.g., `http://localhost:5173/competitions/titanic`).
2.  **Auto-Start**: The application will automatically detect the path, reconstruct the original URL, and begin the ingestion process.

### Chrome Extension

A companion Chrome Extension allows for 1-click ingestion directly from Kaggle pages.

**Installation**:

1.  Go to `chrome://extensions/`.
2.  Enable **Developer mode**.
3.  Click **Load unpacked**.
4.  Select the `chrome-extension` directory in the project root.

**Usage**:

- Navigate to any Kaggle competition or dataset page.
- Click the extension icon.
- Click **Ingest Context** to trigger the local backend.
