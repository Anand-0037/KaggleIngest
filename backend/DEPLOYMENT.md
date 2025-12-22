# KaggleIngest Deployment Guide

## Quick Start (Single Instance)

```bash
docker-compose up --build -d
curl http://localhost:8000/health
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | Set to `production` to disable Swagger |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `RATE_LIMIT` | `60` | Requests per minute per IP |
| `CORS_ORIGINS` | `localhost:3000` | Comma-separated allowed origins |
| `SUBPROCESS_TIMEOUT` | `300` | Kaggle CLI timeout (s) |

## Horizontal Scaling

### Option 1: Docker Compose (Development)

```bash
# Scale to 3 replicas behind nginx
docker-compose -f docker-compose.scaled.yml up --scale api=3 --build -d

# Verify all replicas are running
docker-compose -f docker-compose.scaled.yml ps

# Test load balancing
for i in {1..10}; do curl -s http://localhost:8000/health; done
```

### Option 2: Production Stack (Redis + Prometheus)

```bash
# Deploy full production stack
docker-compose -f docker-compose.prod.yml up --build -d

# Access metrics
curl http://localhost:8000/metrics   # API metrics
open http://localhost:9090           # Prometheus UI
```

### Option 3: Railway (Serverless)

```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
railway login
railway up

# Set production environment
railway variables set ENV=production
railway variables set RATE_LIMIT=200

# Add custom domain
railway domain
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with uptime, version, dependencies |
| `/health/ready` | GET | Readiness check for load balancers |
| `/metrics` | GET | Prometheus metrics |
| `/get-context` | GET/POST | Generate context file |

## Example Request

```bash
curl "http://localhost:8000/get-context?\
url=https://www.kaggle.com/competitions/titanic&\
top_n=5&\
output_format=toon"
```

## Load Testing

```bash
# Install Locust
pip install locust

# Run load test (100 users, 5 minutes)
locust -f tests/locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --html report.html
```

## Production Checklist

- [ ] Set `ENV=production` (disables Swagger)
- [ ] Set `CORS_ORIGINS` to your domain
- [ ] Mount Kaggle credentials read-only (`:ro`)
- [ ] Configure SSL/TLS via nginx
- [ ] Monitor `/metrics` endpoint with Prometheus
- [ ] Set up log aggregation
- [ ] Configure Redis for shared rate limiting
