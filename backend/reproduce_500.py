import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_ingestion(url, top_n=3):
    print(f"Testing ingestion for: {url} (top_n={top_n})")
    payload = {
        "url": url,
        "top_n": top_n,
        "stream": False
    }

    try:
        # Step 1: Trigger Ingestion
        resp = requests.post(f"{BASE_URL}/api/get-context", json=payload)
        print(f"POST Response: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.text}")
            return

        data = resp.json()
        print(f"Status: {data['status']}")

        # Step 2: Poll
        slug = data['slug']
        for i in range(10):
            print(f"Polling {slug}... ({i+1})")
            resp = requests.get(f"{BASE_URL}/api/competitions/{slug}")
            if resp.status_code != 200:
                print(f"Error while polling: {resp.status_code} - {resp.text}")
                break
            data = resp.json()
            print(f"Status: {data['status']}")
            if data['status'] == 'completed':
                print("✅ Ingestion successful!")
                break
            time.sleep(5)

    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="https://www.kaggle.com/competitions/nlp-getting-started")
    parser.add_argument("--top_n", type=int, default=3)
    args = parser.parse_args()

    test_ingestion(args.url, args.top_n)
