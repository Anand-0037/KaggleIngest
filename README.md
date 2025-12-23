# KaggleIngest

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)

> **The Bridge Between Kaggle Data and LLMs.**

KaggleIngest transforms complex Kaggle competitions, datasets, and notebooks into high-quality, token-optimized context for Large Language Models. It solves the "context window" problem by intelligently ranking content and stripping noise.

🌐 **Live Demo:** [https://kaggleingest.com](https://kaggleingest.com)

## Project Structure

```
kaggleingest/
├── frontend/           # React UI (Vite + TanStack Query)
├── backend/            # FastAPI API Server
└── chrome-extension/   # Browser extension for 1-click ingestion
```

## Core Capabilities

- **Smart Context Ranking**: Uses a custom scoring algorithm (`Log(Upvotes) * TimeDecay`) to prioritize high-quality, recent implementation patterns over stale kernels.
- **Async Scalability**: Built on a robust `Redis` + `arq` backend to handle massive datasets and concurrent ingestion jobs without timeout risks.
- **Multi-Format Output**:
  - **`.toon` (Recommended)**: Token Optimized Object Notation. A JSON-like format that uses ~40% fewer tokens than standard JSON.
  - **`.txt`**: Plain text, human-readable summary.
  - **`.md`**: Markdown with syntax highlighting support.
- **Robust Ingestion**: Hardened parsers for legacy `nbformat` v3, multi-encoding CSVs, and resilient error handling.

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Redis (optional, for async job processing)

### Backend Setup

```bash
cd backend
uv sync
uv run uvicorn app:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and will proxy API requests to the backend.

### Chrome Extension

1. Go to `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `chrome-extension` directory
5. (Optional) Right-click the extension icon → **Options** to configure a custom backend URL

## Development

### Frontend Scripts

```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues
npm run format       # Format with Prettier
npm run format:check # Check formatting
npm run test:e2e     # Run Playwright tests
```

### Backend Scripts

```bash
uv run ruff check .        # Lint Python code
uv run ruff format .       # Format Python code
uv run mypy .              # Type check
uv run pytest tests/ -v    # Run tests
```

## API Reference

**Production:** `https://kaggleingest.onrender.com`
**Local:** `http://localhost:8000`

### Submit Ingestion Job

`POST /get-context`

```json
{
  "url": "https://www.kaggle.com/competitions/titanic",
  "top_n": 20,
  "output_format": "toon",
  "dry_run": false
}
```

### Poll Job Status

`GET /jobs/{job_id}`

### Download Result

`GET /jobs/{job_id}/download`

## Architecture

| Component | Technology                    | Purpose                                          |
| --------- | ----------------------------- | ------------------------------------------------ |
| Frontend  | React + Vite + TanStack Query | User interface for job submission and monitoring |
| Backend   | FastAPI + Redis + arq         | Async job processing and Kaggle API integration  |
| Extension | Chrome Extension API          | 1-click ingestion from Kaggle pages              |

## Security

- **Ephemeral Credentials**: User uploads (`kaggle.json`) are processed in memory and never stored permanently.
- **Validation**: Strict file size limits and type checks on all inputs.
- **Sandboxing**: Dockerized deployment ensures isolation.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'feat: add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Code Quality

This project uses:

- **ESLint + Prettier** for JavaScript/React
- **ruff** for Python linting and formatting
- **Playwright** for E2E testing
- **GitHub Actions** for CI/CD

## License

MIT License. Open source and free to use.
