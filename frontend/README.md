# KaggleIngest Frontend

A modern React-based UI for the KaggleIngest tool.

## Features
- **Kaggle Theme**: Clean, data-focused design.
- **Configurable**: Set Top N, output format, and dry-run mode.
- **Secure**: Proxy configuration avoids CORS issues.
- **Complete**: Supports custom `kaggle.json` credential upload.

## Setup

### Prerequisites
- Node.js 16+
- Backend running at `http://localhost:8000`

### Installation
```bash
npm install
```

### Running (Dev)
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

## Deployment
Build for production:
```bash
npm run build
```
Serve the `dist/` folder using Nginx or any static host.
