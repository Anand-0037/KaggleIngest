"""
Locust load test file for KaggleIngest API.
Run with: locust -f tests/locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m --html report.html
"""

from locust import HttpUser, between, task


class KaggleIngestUser(HttpUser):
    """Simulates a user interacting with the KaggleIngest API."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    @task(5)  # 5x weight - most common
    def health_check(self):
        """Test health endpoint - lightweight, frequent."""
        self.client.get("/health")

    @task(3)  # 3x weight
    def get_context_small(self):
        """Test with small notebook count."""
        self.client.get(
            "/get-context",
            params={
                "url": "https://www.kaggle.com/competitions/titanic",
                "top_n": 3,
                "output_format": "txt",
                "dry_run": True  # Dry run for load testing
            }
        )

    @task(1)  # 1x weight - less common
    def get_context_toon(self):
        """Test TOON format output."""
        self.client.get(
            "/get-context",
            params={
                "url": "https://www.kaggle.com/competitions/titanic",
                "top_n": 5,
                "output_format": "toon",
                "dry_run": True
            }
        )

    @task(1)
    def metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        self.client.get("/metrics")

    @task(1)
    def readiness_check(self):
        """Test readiness endpoint."""
        self.client.get("/health/ready")

    def on_start(self):
        """Called when a simulated user starts."""
        # Warm up
        self.client.get("/health")
